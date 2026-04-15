"""Unit tests for YouTubeApiClient — covers ADC regression (issues #25, #27).

Root cause: google-api-python-client unconditionally calls google.auth.default()
in build_from_document() in some deployed versions — even when a developerKey
or credentials are explicitly provided.  The fix (issue #27) replaces the
google-api-python-client dependency entirely with direct urllib REST calls,
eliminating all Google auth machinery from the code path.

These tests verify the new implementation without touching the network.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from mimesis.video_discovery.domain.exceptions import (
    QuotaExceededException,
    YouTubeApiError,
)
from mimesis.video_discovery.infra.youtube_api_client import (
    YouTubeApiClient,
    _yt_get,
)

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_urlopen_response(data: dict) -> MagicMock:
    """Return a context-manager-compatible mock for urllib.request.urlopen."""
    body = json.dumps(data).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _make_http_error(code: int, body: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://example.com",
        code=code,
        msg=f"HTTP {code}",
        hdrs=MagicMock(),  # type: ignore[arg-type]
        fp=BytesIO(body.encode()),
    )


# ── YouTubeApiClient init ─────────────────────────────────────────────────────


class TestYouTubeApiClientInit:
    """Regression: ADC must never be called — issues #25 and #27."""

    def test_init_does_not_call_google_auth_default(self) -> None:
        """Construction must not trigger google.auth.default()."""
        with patch("google.auth.default") as mock_adc:
            YouTubeApiClient(api_key="my-key")
            mock_adc.assert_not_called()

    def test_init_stores_api_key(self) -> None:
        client = YouTubeApiClient(api_key="abc-123")
        assert client._api_key == "abc-123"

    def test_init_makes_no_network_calls(self) -> None:
        """Construction must be free of network I/O."""
        with patch("urllib.request.urlopen") as mock_open:
            YouTubeApiClient(api_key="my-key")
            mock_open.assert_not_called()


# ── _yt_get helper ────────────────────────────────────────────────────────────


class TestYtGet:
    def test_returns_parsed_json(self) -> None:
        payload = {"items": [{"id": "v1"}]}
        with patch("urllib.request.urlopen", return_value=_make_urlopen_response(payload)):
            result = _yt_get("https://example.com")
        assert result == payload

    def test_raises_quota_exceeded_on_403(self) -> None:
        _quota_body = json.dumps(
            {"error": {"errors": [{"reason": "quotaExceeded"}]}}
        )
        with (
            patch("urllib.request.urlopen", side_effect=_make_http_error(403, _quota_body)),
            pytest.raises(QuotaExceededException, match="HTTP 403"),
        ):
            _yt_get("https://example.com")

    def test_raises_youtube_api_error_on_other_http_error(self) -> None:
        with (
            patch("urllib.request.urlopen", side_effect=_make_http_error(500, "server")),
            pytest.raises(YouTubeApiError, match="HTTP 500"),
        ):
            _yt_get("https://example.com")

    def test_raises_youtube_api_error_on_url_error(self) -> None:
        err = urllib.error.URLError(reason="connection refused")
        with (
            patch("urllib.request.urlopen", side_effect=err),
            pytest.raises(YouTubeApiError, match="URL error"),
        ):
            _yt_get("https://example.com")


# ── YouTubeApiClient.search_page ──────────────────────────────────────────────

_SEARCH_RESPONSE = {
    "items": [{"id": {"videoId": "vid1"}}, {"id": {"videoId": "vid2"}}],
    "nextPageToken": "token_next",
}

_VIDEOS_RESPONSE = {
    "items": [
        {
            "id": "vid1",
            "snippet": {
                "title": "Title 1",
                "description": "Desc 1",
                "channelId": "ch1",
                "channelTitle": "Channel 1",
                "publishedAt": "2024-01-01T00:00:00Z",
                "thumbnails": {},
                "categoryId": "22",
            },
            "contentDetails": {"duration": "PT5M"},
            "statistics": {"viewCount": "100", "likeCount": "10"},
        },
        {
            "id": "vid2",
            "snippet": {
                "title": "Title 2",
                "description": "Desc 2",
                "channelId": "ch2",
                "channelTitle": "Channel 2",
                "publishedAt": "2024-02-01T00:00:00Z",
                "thumbnails": {},
                "categoryId": "22",
            },
            "contentDetails": {"duration": "PT3M"},
            "statistics": {"viewCount": "50"},
        },
    ]
}


def _make_search_page_client() -> tuple[YouTubeApiClient, list[MagicMock]]:
    """Build a client whose urlopen calls return search then videos responses."""
    client = YouTubeApiClient(api_key="test-key")
    calls: list[MagicMock] = []

    def _side_effect(url: str) -> MagicMock:
        if "/search" in url:
            resp = _make_urlopen_response(_SEARCH_RESPONSE)
        else:
            resp = _make_urlopen_response(_VIDEOS_RESPONSE)
        calls.append(MagicMock(url=url))
        return resp

    return client, calls, _side_effect  # type: ignore[return-value]


class TestYouTubeApiClientSearchPage:
    def test_returns_video_metadatas(self, mocker) -> None:
        client = YouTubeApiClient(api_key="key")
        responses = [
            _make_urlopen_response(_SEARCH_RESPONSE),
            _make_urlopen_response(_VIDEOS_RESPONSE),
        ]
        mocker.patch("urllib.request.urlopen", side_effect=responses)
        from mimesis.video_discovery.domain.models import SearchQuery

        page = client.search_page(SearchQuery(keyword="test"), page_size=2)
        assert len(page.video_metadatas) == 2
        assert page.next_page_token == "token_next"

    def test_api_key_included_in_request_url(self, mocker) -> None:
        client = YouTubeApiClient(api_key="secret-key")
        captured_urls: list[str] = []

        def _capture(url: str) -> MagicMock:
            captured_urls.append(url)
            if "/search" in url:
                return _make_urlopen_response(_SEARCH_RESPONSE)
            return _make_urlopen_response(_VIDEOS_RESPONSE)

        mocker.patch("urllib.request.urlopen", side_effect=_capture)
        from mimesis.video_discovery.domain.models import SearchQuery

        client.search_page(SearchQuery(keyword="test"), page_size=2)
        assert all("key=secret-key" in u for u in captured_urls)

    def test_returns_empty_page_when_no_search_results(self, mocker) -> None:
        client = YouTubeApiClient(api_key="key")
        mocker.patch(
            "urllib.request.urlopen",
            return_value=_make_urlopen_response({"items": []}),
        )
        from mimesis.video_discovery.domain.models import SearchQuery

        page = client.search_page(SearchQuery(keyword="test"), page_size=5)
        assert page.video_metadatas == []
        assert page.next_page_token is None

    def test_propagates_quota_exceeded_exception(self, mocker) -> None:
        client = YouTubeApiClient(api_key="key")
        _quota_body = json.dumps({"error": {"errors": [{"reason": "quotaExceeded"}]}})
        mocker.patch("urllib.request.urlopen", side_effect=_make_http_error(403, _quota_body))
        from mimesis.video_discovery.domain.models import SearchQuery

        with pytest.raises(QuotaExceededException):
            client.search_page(SearchQuery(keyword="test"), page_size=5)
