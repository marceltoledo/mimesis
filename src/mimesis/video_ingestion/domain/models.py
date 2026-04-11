"""Domain models for BC-02 Video Ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class IngestionStatus(StrEnum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"


@dataclass(frozen=True)
class ArtifactPaths:
    """Canonical Blob paths for one video ingestion job."""

    video_path: str
    audio_path: str
    metadata_path: str


@dataclass(frozen=True)
class VideoDiscoveredPayload:
    """Input event payload consumed from sb-queue-video-discovered."""

    search_job_id: str
    video_id: str
    occurred_at: datetime
    metadata: dict[str, object]

    @property
    def youtube_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass(frozen=True)
class IngestionRecord:
    """Idempotency state persisted in Azure Table Storage."""

    video_id: str
    status: IngestionStatus
    processed_at: datetime | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class IngestionResult:
    """Application-service outcome for one message processing attempt."""

    video_id: str
    status: IngestionStatus
    artifacts_complete: bool
    skipped_as_duplicate: bool


def canonical_paths(video_id: str) -> ArtifactPaths:
    """Build deterministic artifact paths for a video."""
    return ArtifactPaths(
        video_path=f"raw-videos/{video_id}/source.mp4",
        audio_path=f"extracted-audio/{video_id}/audio.mp3",
        metadata_path=f"video-metadata/{video_id}/metadata.json",
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
