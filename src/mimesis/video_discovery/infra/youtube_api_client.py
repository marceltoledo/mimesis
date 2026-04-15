"""YouTube Data API v3 adapter — concrete implementation of YouTubeApiPort.

Direct REST implementation using stdlib urllib. Does NOT use
google-api-python-client, which unconditionally invokes google.auth.default()
in some versions — a call that always fails inside Azure Functions where no
Google Application Default Credentials are present (issues #25, #27).

Two-call strategy per page (ADR-03):
  1. ``search.list``  → videoIds
  2. ``videos.list``  → full metadata batch (1 quota unit)
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, cast

from mimesis.video_discovery.domain.exceptions import (
    QuotaExceededException,
    YouTubeApiError,
)
from mimesis.video_discovery.domain.models import SearchQuery, VideoMetadata
from mimesis.video_discovery.ports.youtube_api_port import SearchPage, YouTubeApiPort

logger = logging.getLogger(__name__)

_YT_API_BASE = "https://www.googleapis.com/youtube/v3"


def _safe_int(value: object) -> int | None:
    """Convert a YouTube statistics string value to int; return None if absent."""
    return int(str(value)) if value is not None else None


def _parse_metadata(item: dict[str, Any]) -> tuple[str, VideoMetadata]:
    """Extract videoId and VideoMetadata from a ``videos.list`` resource item."""
    video_id: str = str(item["id"])
    snippet = cast(dict[str, Any], item.get("snippet", {}))
    details = cast(dict[str, Any], item.get("contentDetails", {}))
    stats = cast(dict[str, Any], item.get("statistics", {}))

    published_at_raw = str(snippet.get("publishedAt", ""))
    published_at = datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))

    thumbnails = cast(dict[str, object], snippet.get("thumbnails", {}))
    tags_raw = snippet.get("tags")
    tags: list[str] | None = None
    if isinstance(tags_raw, list):
        tags = [str(tag) for tag in tags_raw]

    default_language_raw = snippet.get("defaultLanguage")
    default_language = str(default_language_raw) if default_language_raw is not None else None

    metadata = VideoMetadata(
        title=str(snippet.get("title", "")),
        description=str(snippet.get("description", "")),
        channel_id=str(snippet.get("channelId", "")),
        channel_title=str(snippet.get("channelTitle", "")),
        published_at=published_at,
        duration=str(details.get("duration", "")),
        view_count=_safe_int(stats.get("viewCount")) or 0,
        like_count=_safe_int(stats.get("likeCount")),
        thumbnails=thumbnails,
        tags=tags,
        category_id=str(snippet.get("categoryId", "")),
        default_language=default_language,
    )
    return video_id, metadata


def _yt_get(url: str) -> dict[str, Any]:
    """Issue an unauthenticated GET to the YouTube Data API and return parsed JSON.

    The API key is embedded in the URL query string by the caller; no
    Authorization header is needed for developer-key access.

    Raises:
        QuotaExceededException: on HTTP 403 (quota exceeded).
        YouTubeApiError: on any other HTTP or network error.
    """
    try:
        with urllib.request.urlopen(url) as response:  # noqa: S310
            return cast(dict[str, Any], json.loads(response.read().decode()))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        if exc.code == 403:
            raise QuotaExceededException(f"HTTP 403: {body}") from exc
        raise YouTubeApiError(f"HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise YouTubeApiError(f"URL error: {exc.reason}") from exc


class YouTubeApiClient(YouTubeApiPort):
    """Calls YouTube Data API v3 search.list + videos.list per page.

    Uses plain urllib (stdlib) so that no Google authentication library is
    involved at all — avoiding google.auth.default() which fails in Azure
    where there are no Google Application Default Credentials.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search_page(
        self,
        query: SearchQuery,
        page_size: int,
        page_token: str | None = None,
    ) -> SearchPage:
        filters = query.filters

        # ── 1. search.list ───────────────────────────────────────────────────
        search_params: dict[str, str] = {
            "q": query.keyword,
            "part": "snippet",
            "type": "video",
            "maxResults": str(min(page_size, 50)),
            "key": self._api_key,
        }
        if page_token:
            search_params["pageToken"] = page_token
        if filters:
            if filters.language:
                search_params["relevanceLanguage"] = filters.language
            if filters.published_after:
                search_params["publishedAfter"] = filters.published_after.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            if filters.video_duration:
                search_params["videoDuration"] = filters.video_duration
            if filters.region_code:
                search_params["regionCode"] = filters.region_code

        search_url = f"{_YT_API_BASE}/search?{urllib.parse.urlencode(search_params)}"
        search_response = _yt_get(search_url)

        items = cast(list[dict[str, Any]], search_response.get("items", []))
        next_page_token_raw = search_response.get("nextPageToken")
        next_page_token = str(next_page_token_raw) if next_page_token_raw is not None else None

        if not items:
            return SearchPage(video_metadatas=[], next_page_token=None)

        # ── 2. videos.list (batch) ───────────────────────────────────────────
        video_ids = ",".join(str(item["id"]["videoId"]) for item in items)
        videos_params: dict[str, str] = {
            "id": video_ids,
            "part": "snippet,contentDetails,statistics",
            "key": self._api_key,
        }
        videos_url = f"{_YT_API_BASE}/videos?{urllib.parse.urlencode(videos_params)}"
        videos_response = _yt_get(videos_url)

        video_items = cast(list[dict[str, Any]], videos_response.get("items", []))
        results = [_parse_metadata(item) for item in video_items]

        logger.debug(
            "YouTube page fetched | keyword=%r page_token=%s results=%d",
            query.keyword,
            page_token,
            len(results),
        )

        return SearchPage(video_metadatas=results, next_page_token=next_page_token)
