"""Port interface for BC-02 ingestion idempotency ledger."""

from abc import ABC, abstractmethod

from mimesis.video_ingestion.domain.models import IngestionRecord, IngestionStatus


class IngestionLedgerPort(ABC):
    @abstractmethod
    def get(self, video_id: str) -> IngestionRecord | None:
        """Get ledger state for video_id or None if absent."""

    @abstractmethod
    def upsert(
        self, video_id: str, status: IngestionStatus, failure_reason: str | None = None
    ) -> None:
        """Create/update ingestion record."""
