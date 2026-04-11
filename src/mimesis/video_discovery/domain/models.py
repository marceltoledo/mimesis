"""Domain models for the Video Discovery bounded context.

Aggregate Root : SearchJob
Value Objects  : SearchQuery, SearchFilters, VideoMetadata
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar
from uuid import UUID, uuid4


class SearchJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SearchFilters:
    """Optional YouTube search filter parameters."""

    language: str | None = None
    """Instructs the API to prefer results in this language (relevanceLanguage)."""

    published_after: datetime | None = None
    """Return only videos published after this UTC timestamp (RFC 3339)."""

    video_duration: str | None = None
    """Filter by duration category: 'short' (<4 min), 'medium' (4-20 min), 'long' (>20 min)."""

    region_code: str | None = None
    """ISO 3166-1 alpha-2 region code (e.g. 'GB', 'BR')."""

    _VALID_DURATIONS: ClassVar[frozenset[str]] = frozenset({"short", "medium", "long"})

    def __post_init__(self) -> None:
        if self.video_duration is not None and self.video_duration not in self._VALID_DURATIONS:
            raise ValueError(
                f"video_duration must be one of {sorted(self._VALID_DURATIONS)!r}, "
                f"got: {self.video_duration!r}"
            )


@dataclass(frozen=True)
class SearchQuery:
    """A keyword plus optional filter parameters submitted to YouTube."""

    keyword: str
    filters: SearchFilters | None = None

    def __post_init__(self) -> None:
        if not self.keyword or not self.keyword.strip():
            raise ValueError("SearchQuery.keyword must be a non-empty string.")


@dataclass(frozen=True)
class VideoMetadata:
    """Full YouTube Data API v3 metadata for a single video."""

    title: str
    description: str
    channel_id: str
    channel_title: str
    published_at: datetime
    duration: str
    """ISO 8601 duration string, e.g. 'PT10M30S'."""
    view_count: int
    thumbnails: dict[str, object]
    category_id: str
    like_count: int | None = None
    """None when the channel has disabled the like counter."""
    tags: list[str] | None = None
    """None when the uploader did not set any tags."""
    default_language: str | None = None
    """BCP-47 language tag, e.g. 'en'. None when not declared by uploader."""


class SearchJob:
    """Aggregate root that orchestrates a single keyword search run.

    State machine:  PENDING → RUNNING → COMPLETED
                                      ↘ FAILED
    """

    def __init__(
        self,
        search_job_id: UUID,
        query: SearchQuery,
        max_results: int,
        requested_at: datetime,
    ) -> None:
        self.search_job_id = search_job_id
        self.query = query
        self.max_results = max_results
        self.requested_at = requested_at
        self.status = SearchJobStatus.PENDING
        self.pages_fetched: int = 0
        self.new_discoveries: int = 0
        self.duplicates_skipped: int = 0

    # ── state transitions ────────────────────────────────────────────────────

    def mark_running(self) -> None:
        if self.status != SearchJobStatus.PENDING:
            raise ValueError(
                f"Cannot transition to RUNNING from {self.status}. " "Job must be in PENDING state."
            )
        self.status = SearchJobStatus.RUNNING

    def mark_completed(self) -> None:
        if self.status != SearchJobStatus.RUNNING:
            raise ValueError(
                f"Cannot transition to COMPLETED from {self.status}. "
                "Job must be in RUNNING state."
            )
        self.status = SearchJobStatus.COMPLETED

    def mark_failed(self) -> None:
        """Transition to FAILED from any state."""
        self.status = SearchJobStatus.FAILED

    # ── counters ─────────────────────────────────────────────────────────────

    def record_page(self) -> None:
        self.pages_fetched += 1

    def record_discovery(self) -> None:
        self.new_discoveries += 1

    def record_duplicate(self) -> None:
        self.duplicates_skipped += 1

    # ── factory ──────────────────────────────────────────────────────────────

    @classmethod
    def create(cls, query: SearchQuery, max_results: int) -> SearchJob:
        return cls(
            search_job_id=uuid4(),
            query=query,
            max_results=max_results,
            requested_at=datetime.now(UTC),
        )

    def __repr__(self) -> str:
        return (
            f"SearchJob(id={self.search_job_id}, status={self.status}, "
            f"keyword={self.query.keyword!r}, "
            f"new={self.new_discoveries}, dupes={self.duplicates_skipped})"
        )
