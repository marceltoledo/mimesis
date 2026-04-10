"""In-memory fake implementation of YouTubeApiPort for unit tests.

``FakeYouTubeApi`` lets tests inject pre-defined pages of video results.
``page_size`` is respected so that ceiling tests behave like the real API.
Setting ``fail_on_page`` causes a QuotaExceededException on that page index,
enabling AC-05 (quota exhaustion) tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from mimesis.video_discovery.domain.exceptions import QuotaExceededException
from mimesis.video_discovery.domain.models import SearchQuery, VideoMetadata
from mimesis.video_discovery.ports.youtube_api_port import SearchPage, YouTubeApiPort


def _make_metadata(video_id: str) -> VideoMetadata:
    """Return a fully-populated VideoMetadata stub for the given videoId."""
    return VideoMetadata(
        title=f"Title for {video_id}",
        description=f"Description for {video_id}",
        channel_id="ch_test",
        channel_title="Fake Channel",
        published_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        duration="PT8M",
        view_count=1_000,
        like_count=50,
        thumbnails={"default": {"url": f"https://example.com/{video_id}.jpg"}},
        tags=["test"],
        category_id="22",
        default_language="en",
    )


class FakeYouTubeApi(YouTubeApiPort):
    """Configurable fake YouTube API that returns pre-defined pages of videoIds.

    Args:
        pages:        List of pages, each page is a list of videoId strings.
                      Page 0 is returned on the first call, page 1 on the second, etc.
        fail_on_page: If set, raises QuotaExceededException on that page index.
    """

    def __init__(
        self,
        pages: list[list[str]],
        fail_on_page: Optional[int] = None,
    ) -> None:
        self._pages = pages
        self._fail_on_page = fail_on_page
        self.calls: list[dict[str, object]] = []

    def search_page(
        self,
        query: SearchQuery,
        page_size: int,
        page_token: Optional[str] = None,
    ) -> SearchPage:
        page_index = int(page_token) if page_token else 0
        self.calls.append(
            {"query": query, "page_size": page_size, "page_token": page_token, "page_index": page_index}
        )

        if self._fail_on_page is not None and page_index == self._fail_on_page:
            raise QuotaExceededException(f"Simulated quota exhaustion on page {page_index}")

        if page_index >= len(self._pages):
            return SearchPage(video_metadatas=[], next_page_token=None)

        all_video_ids = self._pages[page_index]
        # Respect page_size just as the real YouTube API does
        video_ids = all_video_ids[:page_size]
        results = [(vid, _make_metadata(vid)) for vid in video_ids]

        next_token: Optional[str] = (
            str(page_index + 1) if (page_index + 1) < len(self._pages) else None
        )
        return SearchPage(video_metadatas=results, next_page_token=next_token)
