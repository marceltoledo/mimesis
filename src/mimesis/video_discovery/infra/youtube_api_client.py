"""YouTube Data API v3 adapter — concrete implementation of YouTubeApiPort.

Uses ``google-api-python-client`` with a developer key retrieved from Key Vault.
Two-call strategy per page (ADR-03):
  1. ``search.list``  → videoIds
  2. ``videos.list``  → full metadata batch (1 quota unit)
"""

from __future__ import annotations

import logging
from datetime import datetime

from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from mimesis.video_discovery.domain.exceptions import (
    QuotaExceededException,
    YouTubeApiError,
)
from mimesis.video_discovery.domain.models import SearchQuery, VideoMetadata
from mimesis.video_discovery.ports.youtube_api_port import SearchPage, YouTubeApiPort

logger = logging.getLogger(__name__)

_YT_API_SERVICE = "youtube"
_YT_API_VERSION = "v3"


def _safe_int(value: object) -> int | None:
    """Convert a YouTube statistics string value to int; return None if absent."""
    return int(str(value)) if value is not None else None


def _parse_metadata(item: dict[str, object]) -> tuple[str, VideoMetadata]:
    """Extract videoId and VideoMetadata from a ``videos.list`` resource item."""
    video_id: str = str(item["id"])
    snippet: dict[str, object] = item.get("snippet", {})  # type: ignore[assignment]
    details: dict[str, object] = item.get("contentDetails", {})  # type: ignore[assignment]
    stats: dict[str, object] = item.get("statistics", {})  # type: ignore[assignment]

    published_at_raw = str(snippet.get("publishedAt", ""))
    published_at = datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))

    thumbnails = snippet.get("thumbnails", {})
    tags_raw = snippet.get("tags")
    tags: list[str] | None = list(tags_raw) if tags_raw else None  # type: ignore[arg-type]

    metadata = VideoMetadata(
        title=str(snippet.get("title", "")),
        description=str(snippet.get("description", "")),
        channel_id=str(snippet.get("channelId", "")),
        channel_title=str(snippet.get("channelTitle", "")),
        published_at=published_at,
        duration=str(details.get("duration", "")),
        view_count=_safe_int(stats.get("viewCount")) or 0,
        like_count=_safe_int(stats.get("likeCount")),
        thumbnails=thumbnails,  # type: ignore[arg-type]
        tags=tags,
        category_id=str(snippet.get("categoryId", "")),
        default_language=snippet.get("defaultLanguage") and str(snippet["defaultLanguage"]),
    )
    return video_id, metadata


class YouTubeApiClient(YouTubeApiPort):
    """Calls YouTube Data API v3 search.list + videos.list per page."""

    def __init__(self, api_key: str) -> None:
        self._service = build(
            _YT_API_SERVICE,
            _YT_API_VERSION,
            developerKey=api_key,
            cache_discovery=False,
        )

    def search_page(
        self,
        query: SearchQuery,
        page_size: int,
        page_token: str | None = None,
    ) -> SearchPage:
        filters = query.filters

        # ── 1. search.list ───────────────────────────────────────────────────
        search_kwargs: dict[str, object] = {
            "q": query.keyword,
            "part": "snippet",
            "type": "video",
            "maxResults": min(page_size, 50),
        }
        if page_token:
            search_kwargs["pageToken"] = page_token
        if filters:
            if filters.language:
                search_kwargs["relevanceLanguage"] = filters.language
            if filters.published_after:
                search_kwargs["publishedAfter"] = filters.published_after.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            if filters.video_duration:
                search_kwargs["videoDuration"] = filters.video_duration
            if filters.region_code:
                search_kwargs["regionCode"] = filters.region_code

        try:
            search_response: dict[str, object] = (
                self._service.search().list(**search_kwargs).execute()
            )
        except HttpError as exc:
            if exc.resp.status == 403:  # type: ignore[union-attr]
                raise QuotaExceededException(str(exc)) from exc
            raise YouTubeApiError(str(exc)) from exc

        items: list[dict[str, object]] = search_response.get("items", [])  # type: ignore[assignment]
        next_page_token: str | None = search_response.get("nextPageToken")  # type: ignore[assignment]

        if not items:
            return SearchPage(video_metadatas=[], next_page_token=None)

        # ── 2. videos.list (batch) ───────────────────────────────────────────
        video_ids = ",".join(str(item["id"]["videoId"]) for item in items)  # type: ignore[index]

        try:
            videos_response: dict[str, object] = (
                self._service.videos()
                .list(id=video_ids, part="snippet,contentDetails,statistics")
                .execute()
            )
        except HttpError as exc:
            if exc.resp.status == 403:  # type: ignore[union-attr]
                raise QuotaExceededException(str(exc)) from exc
            raise YouTubeApiError(str(exc)) from exc

        video_items: list[dict[str, object]] = videos_response.get("items", [])  # type: ignore[assignment]
        results = [_parse_metadata(item) for item in video_items]

        logger.debug(
            "YouTube page fetched | keyword=%r page_token=%s results=%d",
            query.keyword,
            page_token,
            len(results),
        )
        return SearchPage(video_metadatas=results, next_page_token=next_page_token)
