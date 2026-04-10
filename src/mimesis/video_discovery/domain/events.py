"""Domain events emitted by the Video Discovery bounded context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from mimesis.video_discovery.domain.models import VideoMetadata


@dataclass(frozen=True)
class VideoDiscovered:
    """Emitted once per unique videoId — globally across all SearchJobs.

    The payload is intentionally self-contained so that any downstream consumer
    (e.g. Video Ingestion) can process the message without additional API calls
    (see AC-04).
    """

    search_job_id: UUID
    video_id: str
    metadata: VideoMetadata
    occurred_at: datetime

    def to_dict(self) -> dict[str, object]:
        """Serialize the event to a JSON-compatible dict for Service Bus transport."""
        return {
            "search_job_id": str(self.search_job_id),
            "video_id": self.video_id,
            "occurred_at": self.occurred_at.isoformat(),
            "metadata": {
                "title": self.metadata.title,
                "description": self.metadata.description,
                "channel_id": self.metadata.channel_id,
                "channel_title": self.metadata.channel_title,
                "published_at": self.metadata.published_at.isoformat(),
                "duration": self.metadata.duration,
                "view_count": self.metadata.view_count,
                "like_count": self.metadata.like_count,
                "thumbnails": self.metadata.thumbnails,
                "tags": self.metadata.tags,
                "category_id": self.metadata.category_id,
                "default_language": self.metadata.default_language,
            },
        }
