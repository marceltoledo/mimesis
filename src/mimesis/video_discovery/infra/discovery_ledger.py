"""Discovery Ledger adapter — Azure Table Storage implementation.

PartitionKey = 'video'
RowKey       = videoId

One Storage Account / one table serves as the global, persistent deduplication
record for all historical SearchJobs (ADR-04).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential

from mimesis.video_discovery.domain.exceptions import DiscoveryLedgerError
from mimesis.video_discovery.ports.discovery_ledger_port import DiscoveryLedgerPort

logger = logging.getLogger(__name__)

_PARTITION_KEY = "video"


class TableStorageDiscoveryLedger(DiscoveryLedgerPort):
    """Azure Table Storage–backed Discovery Ledger."""

    def __init__(self, account_url: str, table_name: str) -> None:
        credential = DefaultAzureCredential()
        service = TableServiceClient(endpoint=account_url, credential=credential)
        self._client = service.get_table_client(table_name)

    def exists(self, video_id: str) -> bool:
        """O(1) point-read check — returns True if videoId is in the ledger."""
        try:
            self._client.get_entity(
                partition_key=_PARTITION_KEY,
                row_key=video_id,
            )
            return True
        except ResourceNotFoundError:
            return False
        except Exception as exc:
            raise DiscoveryLedgerError(
                f"Failed to check Discovery Ledger for video_id={video_id!r}: {exc}"
            ) from exc

    def record(self, video_id: str) -> None:
        """Persist videoId to the ledger.  Idempotent — concurrent writes are silently ignored."""
        entity = {
            "PartitionKey": _PARTITION_KEY,
            "RowKey": video_id,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        try:
            self._client.create_entity(entity=entity)
            logger.debug("Ledger recorded | video_id=%s", video_id)
        except ResourceExistsError:
            # Another concurrent job recorded the same videoId — safe to ignore
            logger.debug("Ledger entry already exists (concurrent write) | video_id=%s", video_id)
        except Exception as exc:
            raise DiscoveryLedgerError(
                f"Failed to record video_id={video_id!r} in Discovery Ledger: {exc}"
            ) from exc
