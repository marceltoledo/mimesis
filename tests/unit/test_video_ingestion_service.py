"""Unit tests for BC-02 Video Ingestion service."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from mimesis.video_ingestion.application.video_ingestion_service import (
    VideoIngestionService,
    parse_video_discovered_payload,
)
from mimesis.video_ingestion.domain.events import VideoIngested
from mimesis.video_ingestion.domain.exceptions import InvalidVideoDiscoveredEventError
from mimesis.video_ingestion.domain.models import (
    ArtifactPaths,
    IngestionRecord,
    IngestionStatus,
    VideoDiscoveredPayload,
    canonical_paths,
)
from mimesis.video_ingestion.ports.artifact_store_port import ArtifactStorePort
from mimesis.video_ingestion.ports.ingested_event_publisher_port import (
    IngestedEventPublisherPort,
)
from mimesis.video_ingestion.ports.ingestion_ledger_port import IngestionLedgerPort
from mimesis.video_ingestion.ports.media_processor_port import MediaProcessorPort


class FakeArtifactStore(ArtifactStorePort):
    def __init__(self) -> None:
        self.uploaded: dict[str, bytes] = {}

    def artifacts_complete(self, paths: ArtifactPaths) -> bool:
        return all(
            path in self.uploaded
            for path in [paths.video_path, paths.audio_path, paths.metadata_path]
        )

    def upload_video(self, path: str, content: bytes) -> str:
        self.uploaded[path] = content
        return f"https://example.blob.core.windows.net/{path}"

    def upload_audio(self, path: str, content: bytes) -> str:
        self.uploaded[path] = content
        return f"https://example.blob.core.windows.net/{path}"

    def upload_metadata(self, path: str, content: bytes) -> str:
        self.uploaded[path] = content
        return f"https://example.blob.core.windows.net/{path}"


class FakeLedger(IngestionLedgerPort):
    def __init__(self, initial: IngestionRecord | None = None) -> None:
        self._record = initial
        self.upserts: list[tuple[str, IngestionStatus, str | None]] = []

    def get(self, video_id: str) -> IngestionRecord | None:
        if self._record and self._record.video_id == video_id:
            return self._record
        return None

    def upsert(self, video_id: str, status: IngestionStatus, failure_reason: str | None = None) -> None:
        self.upserts.append((video_id, status, failure_reason))
        self._record = IngestionRecord(video_id=video_id, status=status)


class FakeMediaProcessor(MediaProcessorPort):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.download_calls: list[str] = []
        self.extract_calls = 0

    def download_source_video(self, youtube_url: str) -> bytes:
        self.download_calls.append(youtube_url)
        if self.fail:
            raise RuntimeError("download failed")
        return b"video"

    def extract_audio_mp3(self, source_video_bytes: bytes) -> bytes:
        self.extract_calls += 1
        if self.fail:
            raise RuntimeError("extract failed")
        return b"audio"


class FakePublisher(IngestedEventPublisherPort):
    def __init__(self) -> None:
        self.published: list[VideoIngested] = []

    def publish(self, event: VideoIngested) -> None:
        self.published.append(event)



def _sample_payload(video_id: str = "vid123") -> VideoDiscoveredPayload:
    return VideoDiscoveredPayload(
        search_job_id="job-1",
        video_id=video_id,
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        metadata={"title": "Video"},
    )


class TestIngestionService:
    def test_processes_new_video_and_emits_event(self) -> None:
        store = FakeArtifactStore()
        ledger = FakeLedger()
        media = FakeMediaProcessor()
        publisher = FakePublisher()

        service = VideoIngestionService(
            artifact_store=store,
            ledger=ledger,
            media_processor=media,
            event_publisher=publisher,
        )

        result = service.ingest_discovered_video(_sample_payload())

        assert result.status == IngestionStatus.COMPLETED
        assert result.artifacts_complete is True
        assert result.skipped_as_duplicate is False
        assert len(publisher.published) == 1

        paths = canonical_paths("vid123")
        assert paths.video_path in store.uploaded
        assert paths.audio_path in store.uploaded
        assert paths.metadata_path in store.uploaded

    def test_skips_duplicate_when_completed_and_artifacts_exist(self) -> None:
        store = FakeArtifactStore()
        paths = canonical_paths("vid123")
        store.uploaded[paths.video_path] = b"v"
        store.uploaded[paths.audio_path] = b"a"
        store.uploaded[paths.metadata_path] = b"m"

        ledger = FakeLedger(
            initial=IngestionRecord(video_id="vid123", status=IngestionStatus.COMPLETED)
        )
        media = FakeMediaProcessor()
        publisher = FakePublisher()

        service = VideoIngestionService(
            artifact_store=store,
            ledger=ledger,
            media_processor=media,
            event_publisher=publisher,
        )

        result = service.ingest_discovered_video(_sample_payload())

        assert result.skipped_as_duplicate is True
        assert media.download_calls == []
        assert publisher.published == []

    def test_reprocesses_when_ledger_completed_but_artifact_missing(self) -> None:
        store = FakeArtifactStore()
        paths = canonical_paths("vid123")
        store.uploaded[paths.video_path] = b"v"
        store.uploaded[paths.audio_path] = b"a"

        ledger = FakeLedger(
            initial=IngestionRecord(video_id="vid123", status=IngestionStatus.COMPLETED)
        )
        media = FakeMediaProcessor()
        publisher = FakePublisher()

        service = VideoIngestionService(
            artifact_store=store,
            ledger=ledger,
            media_processor=media,
            event_publisher=publisher,
        )

        result = service.ingest_discovered_video(_sample_payload())

        assert result.skipped_as_duplicate is False
        assert media.download_calls == ["https://www.youtube.com/watch?v=vid123"]
        assert len(publisher.published) == 1

    def test_marks_failed_on_processing_error(self) -> None:
        store = FakeArtifactStore()
        ledger = FakeLedger()
        media = FakeMediaProcessor(fail=True)
        publisher = FakePublisher()

        service = VideoIngestionService(
            artifact_store=store,
            ledger=ledger,
            media_processor=media,
            event_publisher=publisher,
        )

        with pytest.raises(RuntimeError):
            service.ingest_discovered_video(_sample_payload())

        assert ledger.upserts[-1][1] == IngestionStatus.FAILED


class TestPayloadParsing:
    def test_parses_valid_payload(self) -> None:
        raw = json.dumps(
            {
                "search_job_id": "job-1",
                "video_id": "vid123",
                "occurred_at": "2026-01-01T00:00:00+00:00",
                "metadata": {"title": "x"},
            }
        )
        parsed = parse_video_discovered_payload(raw)
        assert parsed.video_id == "vid123"

    def test_rejects_missing_fields(self) -> None:
        raw = json.dumps({"video_id": "vid123"})
        with pytest.raises(InvalidVideoDiscoveredEventError):
            parse_video_discovered_payload(raw)
