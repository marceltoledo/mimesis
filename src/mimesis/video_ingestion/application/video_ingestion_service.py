"""Application service for BC-02 Video Ingestion."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from mimesis.video_ingestion.domain.events import VideoIngested
from mimesis.video_ingestion.domain.exceptions import InvalidVideoDiscoveredEventError
from mimesis.video_ingestion.domain.models import (
    ArtifactPaths,
    IngestionResult,
    IngestionStatus,
    VideoDiscoveredPayload,
    canonical_paths,
    utcnow,
)
from mimesis.video_ingestion.ports.artifact_store_port import ArtifactStorePort
from mimesis.video_ingestion.ports.ingested_event_publisher_port import IngestedEventPublisherPort
from mimesis.video_ingestion.ports.ingestion_ledger_port import IngestionLedgerPort
from mimesis.video_ingestion.ports.media_processor_port import MediaProcessorPort

logger = logging.getLogger(__name__)


class VideoIngestionService:
    """Processes one VideoDiscovered event and emits VideoIngested on success."""

    def __init__(
        self,
        *,
        artifact_store: ArtifactStorePort,
        ledger: IngestionLedgerPort,
        media_processor: MediaProcessorPort,
        event_publisher: IngestedEventPublisherPort,
    ) -> None:
        self._artifact_store = artifact_store
        self._ledger = ledger
        self._media_processor = media_processor
        self._event_publisher = event_publisher

    def ingest_discovered_video(self, payload: VideoDiscoveredPayload) -> IngestionResult:
        paths = canonical_paths(payload.video_id)
        record = self._ledger.get(payload.video_id)

        if (
            record is not None
            and record.status == IngestionStatus.COMPLETED
            and self._artifact_store.artifacts_complete(paths)
        ):
            logger.info("Skipping already-ingested video | video_id=%s", payload.video_id)
            return IngestionResult(
                video_id=payload.video_id,
                status=IngestionStatus.COMPLETED,
                artifacts_complete=True,
                skipped_as_duplicate=True,
            )

        self._ledger.upsert(payload.video_id, IngestionStatus.PROCESSING)
        ingested_at = utcnow()

        try:
            source_video = self._media_processor.download_source_video(payload.youtube_url)
            video_url = self._artifact_store.upload_video(paths.video_path, source_video)

            audio_mp3 = self._media_processor.extract_audio_mp3(source_video)
            audio_url = self._artifact_store.upload_audio(paths.audio_path, audio_mp3)

            metadata_json = _build_ingestion_metadata_json(payload, ingested_at, paths)
            metadata_url = self._artifact_store.upload_metadata(
                paths.metadata_path,
                metadata_json,
            )

            complete = self._artifact_store.artifacts_complete(paths)
            if not complete:
                raise RuntimeError("Artifact completeness validation failed after upload.")

            self._ledger.upsert(payload.video_id, IngestionStatus.COMPLETED)

            event = VideoIngested.build(
                search_job_id=payload.search_job_id,
                video_id=payload.video_id,
                ingested_at=ingested_at,
                paths=paths,
                audio_url=audio_url,
                metadata_url=metadata_url,
                video_url=video_url,
            )
            self._event_publisher.publish(event)

            return IngestionResult(
                video_id=payload.video_id,
                status=IngestionStatus.COMPLETED,
                artifacts_complete=True,
                skipped_as_duplicate=False,
            )
        except Exception as exc:
            self._ledger.upsert(
                payload.video_id,
                IngestionStatus.FAILED,
                failure_reason=str(exc),
            )
            raise


def parse_video_discovered_payload(raw: str) -> VideoDiscoveredPayload:
    """Validate and parse queue payload into a typed object."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InvalidVideoDiscoveredEventError("Invalid JSON payload") from exc

    required = ["search_job_id", "video_id", "occurred_at", "metadata"]
    missing = [key for key in required if key not in data]
    if missing:
        raise InvalidVideoDiscoveredEventError(f"Missing required fields: {', '.join(missing)}")

    if not isinstance(data["metadata"], dict):
        raise InvalidVideoDiscoveredEventError("metadata must be an object")

    try:
        occurred_at = datetime.fromisoformat(str(data["occurred_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidVideoDiscoveredEventError("occurred_at must be an ISO-8601 datetime") from exc

    return VideoDiscoveredPayload(
        search_job_id=str(data["search_job_id"]),
        video_id=str(data["video_id"]),
        occurred_at=occurred_at,
        metadata=data["metadata"],
    )


def _build_ingestion_metadata_json(
    payload: VideoDiscoveredPayload,
    ingested_at: datetime,
    paths: ArtifactPaths,
) -> bytes:
    body = {
        "video_id": payload.video_id,
        "search_job_id": payload.search_job_id,
        "discovered_at": payload.occurred_at.isoformat(),
        "ingested_at": ingested_at.isoformat(),
        "source": {
            "youtube_url": payload.youtube_url,
            "video_path": paths.video_path,
            "audio_path": paths.audio_path,
            "metadata_path": paths.metadata_path,
        },
        "metadata": payload.metadata,
    }
    return json.dumps(body, ensure_ascii=False).encode("utf-8")
