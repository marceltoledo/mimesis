"""Unit tests for BC-01 discovery runtime configuration defaults."""

from __future__ import annotations

from mimesis.video_discovery.config import VideoDiscoveryConfig


def test_default_max_results_falls_back_to_15(monkeypatch) -> None:
    monkeypatch.setenv("MIMESIS_KEY_VAULT_URL", "https://example.vault.azure.net/")
    monkeypatch.setenv("MIMESIS_STORAGE_ACCOUNT_URL", "https://example.table.core.windows.net/")
    monkeypatch.setenv("MIMESIS_SERVICE_BUS_NAMESPACE", "example.servicebus.windows.net")
    monkeypatch.setenv("MIMESIS_APP_INSIGHTS_CONNECTION_STRING", "InstrumentationKey=test")
    monkeypatch.delenv("MIMESIS_DEFAULT_MAX_RESULTS", raising=False)

    cfg = VideoDiscoveryConfig.from_env()
    assert cfg.default_max_results == 15
