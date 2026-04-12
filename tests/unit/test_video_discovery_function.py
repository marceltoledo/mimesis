"""Unit tests for BC-01 HTTP function request parsing helpers."""

from __future__ import annotations

import pytest

from mimesis.video_discovery.function_app import _build_query, _resolve_max_results


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
