"""Unit tests for BC-01 HTTP function request parsing helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mimesis.video_discovery.function_app import _build_query, _resolve_max_results, video_discovery


class TestResolveMaxResults:
    def test_uses_default_when_field_omitted(self) -> None:
        payload: dict[str, object] = {"keyword": "story"}
        assert _resolve_max_results(payload, default_value=15) == 15

    def test_uses_explicit_value(self) -> None:
        payload: dict[str, object] = {"keyword": "story", "max_results": 3}
        assert _resolve_max_results(payload, default_value=15) == 3

    def test_rejects_non_int(self) -> None:
        payload: dict[str, object] = {"keyword": "story", "max_results": "3"}
        with pytest.raises(ValueError):
            _resolve_max_results(payload, default_value=15)


class TestBuildQuery:
    def test_builds_query_without_filters(self) -> None:
        query = _build_query({"keyword": "  ai news "})
        assert query.keyword == "ai news"
        assert query.filters is None

    def test_builds_query_with_filters(self) -> None:
        query = _build_query(
            {
                "keyword": "ai",
                "filters": {
                    "language": "en",
                    "video_duration": "short",
                    "region_code": "GB",
                },
            }
        )
        assert query.filters is not None
        assert query.filters.language == "en"
        assert query.filters.video_duration == "short"
        assert query.filters.region_code == "GB"

    def test_rejects_missing_keyword(self) -> None:
        with pytest.raises(ValueError):
            _build_query({"keyword": "  "})


_REQUIRED_ENV = {
    "MIMESIS_KEY_VAULT_URL": "https://example.vault.azure.net/",
    "MIMESIS_STORAGE_ACCOUNT_URL": "https://example.table.core.windows.net/",
    "MIMESIS_SERVICE_BUS_NAMESPACE": "example.servicebus.windows.net",
    "MIMESIS_APP_INSIGHTS_CONNECTION_STRING": "InstrumentationKey=test",
}


class TestBuildIdHeader:
    def _make_request(self, body: object) -> MagicMock:
        req = MagicMock()
        req.get_json.return_value = body
        return req

    def test_400_response_includes_build_id_header(self, monkeypatch) -> None:
        for key, value in _REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("BUILD_ID", "a3f9c1b2-47")

        req = self._make_request({"keyword": "  "})  # blank keyword → ValueError → 400

        with patch("mimesis.video_discovery.function_app.configure_observability"):
            response = video_discovery(req)

        assert response.status_code == 400
        assert response.headers.get("X-Build-Id") == "a3f9c1b2-47"

    def test_build_id_header_defaults_to_unknown_when_env_absent(self, monkeypatch) -> None:
        for key, value in _REQUIRED_ENV.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("BUILD_ID", raising=False)

        req = self._make_request({"keyword": "  "})  # blank keyword → ValueError → 400

        with patch("mimesis.video_discovery.function_app.configure_observability"):
            response = video_discovery(req)

        assert response.headers.get("X-Build-Id") == "unknown"
