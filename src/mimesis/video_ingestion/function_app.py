"""Azure Functions Service Bus trigger for BC-02 Video Ingestion."""

from __future__ import annotations

import logging

import azure.functions as func

from mimesis.shared.observability import configure_observability
from mimesis.video_ingestion.application.video_ingestion_service import (
    VideoIngestionService,
    parse_video_discovered_payload,
)
from mimesis.video_ingestion.config import VideoIngestionConfig
from mimesis.video_ingestion.domain.exceptions import (
    InvalidVideoDiscoveredEventError,
    VideoIngestionError,
)
from mimesis.video_ingestion.infra.blob_artifact_store import BlobArtifactStore
from mimesis.video_ingestion.infra.ingestion_ledger import TableIngestionLedger
from mimesis.video_ingestion.infra.media_processor import PytubefixMediaProcessor
from mimesis.video_ingestion.infra.video_ingested_event_publisher import (
    ServiceBusVideoIngestedPublisher,
)

logger = logging.getLogger(__name__)

app = func.FunctionApp()

_config = VideoIngestionConfig.from_env()
configure_observability(
    connection_string=_config.app_insights_connection_string,
    service_name="mimesis-video-ingestion",
    build_id=_config.build_id,
)

_service = VideoIngestionService(
    artifact_store=BlobArtifactStore(account_url=_config.storage_account_url),
    ledger=TableIngestionLedger(
        account_url=_config.storage_account_url.replace(".blob.", ".table."),
        table_name=_config.ingestion_ledger_table,
    ),
    media_processor=PytubefixMediaProcessor(),
    event_publisher=ServiceBusVideoIngestedPublisher(
        fully_qualified_namespace=_config.service_bus_namespace,
        queue_name=_config.video_ingested_queue,
    ),
)


@app.function_name(name="VideoIngestion")
@app.service_bus_queue_trigger(
    arg_name="message",
    queue_name="sb-queue-video-discovered",
    connection="MIMESIS_SERVICE_BUS",
)
def video_ingestion(message: func.ServiceBusMessage) -> None:
    """Consume VideoDiscovered and persist durable artifacts."""
    raw = message.get_body().decode("utf-8")
    message_id = message.message_id

    try:
        payload = parse_video_discovered_payload(raw)
        result = _service.ingest_discovered_video(payload)
        logger.info(
            "Video ingestion completed | message_id=%s video_id=%s skipped_duplicate=%s",
            message_id,
            payload.video_id,
            result.skipped_as_duplicate,
        )
    except InvalidVideoDiscoveredEventError:
        # Invalid schema is treated as a non-retryable poison message.
        logger.exception("Invalid VideoDiscovered payload | message_id=%s", message_id)
        raise
    except VideoIngestionError:
        logger.exception("Ingestion failed | message_id=%s", message_id)
        raise
    except Exception:
        logger.exception("Unexpected ingestion failure | message_id=%s", message_id)
        raise
