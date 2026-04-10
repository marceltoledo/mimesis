"""Integration tests — Azure Table Storage Discovery Ledger.

Require a live Azure Storage Account with the Terraform-provisioned table.
Set environment variables from Terraform outputs before running.

Run with: pytest -m integration tests/integration/test_discovery_ledger_integration.py
"""

from __future__ import annotations

import os
import uuid

import pytest

from mimesis.video_discovery.infra.discovery_ledger import TableStorageDiscoveryLedger


def _get_ledger() -> TableStorageDiscoveryLedger:
    return TableStorageDiscoveryLedger(
        account_url=os.environ["MIMESIS_STORAGE_ACCOUNT_URL"],
        table_name=os.environ.get("MIMESIS_DISCOVERY_LEDGER_TABLE", "discoveryLedger"),
    )


@pytest.mark.integration
class TestDiscoveryLedgerLive:
    def test_ac06_new_video_not_in_ledger(self) -> None:
        """AC-06: A brand-new videoId must not exist in the ledger."""
        ledger = _get_ledger()
        novel_id = f"test_{uuid.uuid4().hex}"
        assert not ledger.exists(novel_id)

    def test_ac06_recorded_video_is_found(self) -> None:
        """AC-06: After recording, exists() must return True."""
        ledger = _get_ledger()
        novel_id = f"test_{uuid.uuid4().hex}"
        ledger.record(novel_id)
        assert ledger.exists(novel_id)

    def test_record_is_idempotent(self) -> None:
        """record() called twice for the same videoId must not raise."""
        ledger = _get_ledger()
        novel_id = f"test_{uuid.uuid4().hex}"
        ledger.record(novel_id)
        ledger.record(novel_id)  # must not raise
        assert ledger.exists(novel_id)
