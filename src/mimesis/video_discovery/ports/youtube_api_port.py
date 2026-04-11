"""Port interface: YouTube Data API v3 search adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from mimesis.video_discovery.domain.models import SearchQuery, VideoMetadata


@dataclass(frozen=True)
class SearchPage:
    """One page of YouTube search results with full metadata attached.

    ``video_metadatas`` contains at most ``page_size`` entries as requested.
    ``next_page_token`` is ``None`` when there are no further pages.
    """

    video_metadatas: list[tuple[str, VideoMetadata]]
    """List of (videoId, VideoMetadata) tuples for this page."""

    next_page_token: str | None
    """Opaque cursor to pass on the next call, or None when exhausted."""


class YouTubeApiPort(ABC):
    """Contract for fetching paginated YouTube search results with enriched metadata."""

    @abstractmethod
    def search_page(
        self,
        query: SearchQuery,
        page_size: int,
        page_token: str | None = None,
    ) -> SearchPage:
        """Fetch a single page of search results.

        Performs two API calls internally:
          1. ``search.list`` — returns videoIds for the given query / page.
          2. ``videos.list`` — batch-enriches those IDs with full metadata.

        Args:
            query:      The keyword and optional filters.
            page_size:  Maximum number of results to return (≤50).
            page_token: Opaque pagination cursor from the previous call.

        Raises:
            QuotaExceededException: When the YouTube API returns HTTP 403 quotaExceeded.
            YouTubeApiError:        For any other non-retryable API failure.
        """
