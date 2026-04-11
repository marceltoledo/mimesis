"""Azure Table Storage ingestion ledger adapter."""

from __future__ import annotations

from datetime import UTC, datetime

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient, UpdateMode
from azure.identity import DefaultAzureCredential

from mimesis.video_ingestion.domain.exceptions import IngestionLedgerError
from mimesis.video_ingestion.domain.models import IngestionRecord, IngestionStatus
from mimesis.video_ingestion.ports.ingestion_ledger_port import IngestionLedgerPort


class TableIngestionLedger(IngestionLedgerPort):
    """Maintains ingestion idempotency records keyed by video_id."""

    def __init__(self, account_url: str, table_name: str) -> None:
        credential = DefaultAzureCredential()
        service = TableServiceClient(endpoint=account_url, credential=credential)
        self._client = service.get_table_client(table_name)

    def get(self, video_id: str) -> IngestionRecord | None:
        try:
            entity = self._client.get_entity(partition_key="video", row_key=video_id)
        except ResourceNotFoundError:
            return None
        except Exception as exc:
            raise IngestionLedgerError(f"Failed to read ingestion ledger for '{video_id}': {exc}") from exc

        status_raw = str(entity.get("status", IngestionStatus.PENDING.value))
        try:
            status = IngestionStatus(status_raw)
        except ValueError:
            status = IngestionStatus.PENDING

        processed_raw = entity.get("processed_at")
        processed_at = None
        if isinstance(processed_raw, str):
            try:
                processed_at = datetime.fromisoformat(processed_raw.replace("Z", "+00:00"))
            except ValueError:
                processed_at = None

        return IngestionRecord(
            video_id=video_id,
            status=status,
            processed_at=processed_at,
            failure_reason=entity.get("failure_reason"),
        )

    def upsert(self, video_id: str, status: IngestionStatus, failure_reason: str | None = None) -> None:
        entity = {
            "PartitionKey": "video",
            "RowKey": video_id,
            "status": status.value,
            "processed_at": datetime.now(UTC).isoformat(),
            "failure_reason": failure_reason,
        }
        try:
            self._client.upsert_entity(mode=UpdateMode.MERGE, entity=entity)
        except Exception as exc:
            raise IngestionLedgerError(f"Failed to upsert ingestion ledger for '{video_id}': {exc}") from exc
