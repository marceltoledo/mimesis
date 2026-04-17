"""Unit tests for BC-02 Service Bus trigger handler."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import azure.functions as func
import pytest

from mimesis.video_ingestion.domain.exceptions import (
    InvalidVideoDiscoveredEventError,
    VideoIngestionError,
)
from mimesis.video_ingestion.domain.models import IngestionResult, IngestionStatus

_REQUIRED_ENV = {
    "MIMESIS_STORAGE_ACCOUNT_URL": "https://example.blob.core.windows.net/",
    "MIMESIS_SERVICE_BUS_NAMESPACE": "example.servicebus.windows.net",
    "MIMESIS_APP_INSIGHTS_CONNECTION_STRING": "InstrumentationKey=test",
}

# Patch configure_azure_monitor to prevent the Azure Monitor SDK from
# attempting real connections during module-level initialisation.
with (
    patch.dict(os.environ, _REQUIRED_ENV),
    patch("mimesis.shared.observability.configure_azure_monitor"),
):
    import mimesis.video_ingestion.function_app as _function_module
    from mimesis.video_ingestion.function_app import video_ingestion

_VALID_BODY = (
    '{"search_job_id": "job-001", "video_id": "dQw4w9WgXcQ",'
    ' "occurred_at": "2024-06-01T12:00:00Z", "metadata": {"title": "Test"}}'
)


def _make_message(body: str = _VALID_BODY, message_id: str = "msg-001") -> MagicMock:
    msg = MagicMock(spec=func.ServiceBusMessage)
    msg.get_body.return_value = body.encode("utf-8")
    msg.message_id = message_id
    return msg


class TestVideoIngestionHandler:
    def test_successful_ingestion_does_not_raise(self) -> None:
        result = IngestionResult(
            video_id="dQw4w9WgXcQ",
            status=IngestionStatus.COMPLETED,
            artifacts_complete=True,
            skipped_as_duplicate=False,
        )
        mock_service = MagicMock()
        mock_service.ingest_discovered_video.return_value = result

        with patch.object(_function_module, "_service", mock_service):
            video_ingestion(_make_message())

        mock_service.ingest_discovered_video.assert_called_once()

    def test_successful_ingestion_logs_video_id_and_duplicate_flag(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        result = IngestionResult(
            video_id="dQw4w9WgXcQ",
            status=IngestionStatus.COMPLETED,
            artifacts_complete=True,
            skipped_as_duplicate=True,
        )
        mock_service = MagicMock()
        mock_service.ingest_discovered_video.return_value = result

        with patch.object(_function_module, "_service", mock_service):
            import logging

            with caplog.at_level(logging.INFO, logger="mimesis.video_ingestion.function_app"):
                video_ingestion(_make_message())

        assert "dQw4w9WgXcQ" in caplog.text
        assert "skipped_duplicate=True" in caplog.text

    def test_invalid_payload_reraises_as_poison_message(self) -> None:
        mock_service = MagicMock()

        with (
            patch.object(_function_module, "_service", mock_service),
            patch.object(
                _function_module,
                "parse_video_discovered_payload",
                side_effect=InvalidVideoDiscoveredEventError("bad schema"),
            ),
            pytest.raises(InvalidVideoDiscoveredEventError),
        ):
            video_ingestion(_make_message(body="not-valid-json"))

        mock_service.ingest_discovered_video.assert_not_called()

    def test_ingestion_error_is_reraised_for_retry(self) -> None:
        mock_service = MagicMock()
        mock_service.ingest_discovered_video.side_effect = VideoIngestionError("download failed")

        with (
            patch.object(_function_module, "_service", mock_service),
            pytest.raises(VideoIngestionError),
        ):
            video_ingestion(_make_message())

    def test_unexpected_exception_is_reraised(self) -> None:
        mock_service = MagicMock()
        mock_service.ingest_discovered_video.side_effect = RuntimeError("unexpected")

        with (
            patch.object(_function_module, "_service", mock_service),
            pytest.raises(RuntimeError, match="unexpected"),
        ):
            video_ingestion(_make_message())

    def test_message_id_appears_in_error_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        mock_service = MagicMock()
        mock_service.ingest_discovered_video.side_effect = VideoIngestionError("oops")

        with (
            patch.object(_function_module, "_service", mock_service),
            pytest.raises(VideoIngestionError),
        ):
            import logging

            with caplog.at_level(logging.ERROR, logger="mimesis.video_ingestion.function_app"):
                video_ingestion(_make_message(message_id="abc-123"))

        assert "abc-123" in caplog.text
