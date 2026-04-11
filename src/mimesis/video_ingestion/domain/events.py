"""Domain events for BC-02 Video Ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mimesis.video_ingestion.domain.models import ArtifactPaths


@dataclass(frozen=True)
class VideoIngested:
    """Event emitted once video/audio/metadata artifacts are durably available."""

    schema_version: str
    search_job_id: str
    video_id: str
    ingested_at: datetime
    audio_url: str
    audio_path: str
    metadata_url: str
    metadata_path: str
    video_url: str
    video_path: str

    @classmethod
    def build(
        cls,
        *,
        search_job_id: str,
        video_id: str,
        ingested_at: datetime,
        paths: ArtifactPaths,
        audio_url: str,
        metadata_url: str,
        video_url: str,
    ) -> VideoIngested:
        return cls(
            schema_version="v1",
            search_job_id=search_job_id,
            video_id=video_id,
            ingested_at=ingested_at,
            audio_url=audio_url,
            audio_path=paths.audio_path,
            metadata_url=metadata_url,
            metadata_path=paths.metadata_path,
            video_url=video_url,
            video_path=paths.video_path,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "search_job_id": self.search_job_id,
            "video_id": self.video_id,
            "ingested_at": self.ingested_at.isoformat(),
            "audio_url": self.audio_url,
            "audio_path": self.audio_path,
            "metadata_url": self.metadata_url,
            "metadata_path": self.metadata_path,
            "video_url": self.video_url,
            "video_path": self.video_path,
        }
