"""Port interface: Discovery Ledger — globally-scoped deduplication store."""

from abc import ABC, abstractmethod


class DiscoveryLedgerPort(ABC):
    """Contract for the globally-scoped Discovery Ledger.

    The ledger is the authoritative record of every ``videoId`` that has ever
    been emitted as a ``VideoDiscovered`` event.  It prevents duplicate events
    across all historical ``SearchJob`` runs (AC-06).

    Backed by Azure Table Storage (``PartitionKey='video'``, ``RowKey=videoId``).
    """

    @abstractmethod
    def exists(self, video_id: str) -> bool:
        """Return ``True`` if *video_id* has already been discovered."""

    @abstractmethod
    def record(self, video_id: str) -> None:
        """Persist *video_id* to the ledger.

        Implementations MUST be idempotent — a duplicate write (race condition)
        must not raise an exception.

        Raises:
            DiscoveryLedgerError: For unexpected storage failures.
        """
