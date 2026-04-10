"""In-memory fake implementation of DiscoveryLedgerPort for unit tests."""

from __future__ import annotations

from mimesis.video_discovery.ports.discovery_ledger_port import DiscoveryLedgerPort


class FakeDiscoveryLedger(DiscoveryLedgerPort):
    """Thread-unsafe in-memory ledger suitable for unit tests.

    Args:
        preexisting: Optional set of videoIds to pre-populate (simulates prior discoveries).
    """

    def __init__(self, preexisting: set[str] | None = None) -> None:
        self._store: set[str] = set(preexisting or [])
        self.recorded: list[str] = []
        """Ordered log of every videoId passed to record(), for assertion purposes."""

    def exists(self, video_id: str) -> bool:
        return video_id in self._store

    def record(self, video_id: str) -> None:
        self._store.add(video_id)
        self.recorded.append(video_id)
