"""Unit tests for BC-02 video ingestion runtime configuration defaults."""

from __future__ import annotations

from mimesis.video_ingestion.config import VideoIngestionConfig

_REQUIRED_VARS = {
    "MIMESIS_STORAGE_ACCOUNT_URL": "https://example.table.core.windows.net/",
    "MIMESIS_SERVICE_BUS_NAMESPACE": "example.servicebus.windows.net",
    "MIMESIS_APP_INSIGHTS_CONNECTION_STRING": "InstrumentationKey=test",
    "MIMESIS_KEY_VAULT_URL": "https://example.vault.azure.net/",
}


def _set_required(monkeypatch) -> None:
    for key, value in _REQUIRED_VARS.items():
        monkeypatch.setenv(key, value)


def test_build_id_defaults_to_unknown_when_env_not_set(monkeypatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.delenv("BUILD_ID", raising=False)

    cfg = VideoIngestionConfig.from_env()
    assert cfg.build_id == "unknown"


def test_build_id_read_from_env(monkeypatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("BUILD_ID", "a3f9c1b2-47")

    cfg = VideoIngestionConfig.from_env()
    assert cfg.build_id == "a3f9c1b2-47"


def test_cookies_secret_name_defaults_to_youtube_cookies(monkeypatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.delenv("MIMESIS_YOUTUBE_COOKIES_SECRET", raising=False)

    cfg = VideoIngestionConfig.from_env()
    assert cfg.cookies_secret_name == "youtube-cookies"


def test_cookies_secret_name_read_from_env(monkeypatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.setenv("MIMESIS_YOUTUBE_COOKIES_SECRET", "yt-cookies-prod")

    cfg = VideoIngestionConfig.from_env()
    assert cfg.cookies_secret_name == "yt-cookies-prod"


def test_missing_key_vault_url_raises(monkeypatch) -> None:
    _set_required(monkeypatch)
    monkeypatch.delenv("MIMESIS_KEY_VAULT_URL", raising=False)

    import pytest

    with pytest.raises(RuntimeError, match="MIMESIS_KEY_VAULT_URL"):
        VideoIngestionConfig.from_env()
