"""Unit tests for YouTubeApiClient — covers ADC regression (issue #25).

These tests verify that YouTubeApiClient construction does NOT trigger
google.auth.default() (which fails in Azure where no Google ADC is present).
The googleapiclient.discovery.build call is patched to avoid network I/O.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httplib2

from mimesis.video_discovery.infra.youtube_api_client import YouTubeApiClient


class TestYouTubeApiClientInit:
    """Regression tests for issue #25 — missing Google ADC in Azure."""

    def test_init_does_not_call_google_auth_default(self) -> None:
        """Constructing YouTubeApiClient must never invoke google.auth.default().

        If google.auth.default() is called the function will fail in Azure
        where no Google Application Default Credentials are configured.
        """
        with (
            patch("mimesis.video_discovery.infra.youtube_api_client.build") as mock_build,
            patch("google.auth.default") as mock_adc,
        ):
            mock_build.return_value = MagicMock()

            YouTubeApiClient(api_key="fake-api-key")

            mock_adc.assert_not_called()

    def test_init_passes_httplib2_http_to_build(self) -> None:
        """build() must receive an httplib2.Http instance to bypass ADC lookup."""
        with patch("mimesis.video_discovery.infra.youtube_api_client.build") as mock_build:
            mock_build.return_value = MagicMock()

            YouTubeApiClient(api_key="fake-api-key")

            _, kwargs = mock_build.call_args
            assert isinstance(kwargs.get("http"), httplib2.Http)

    def test_init_passes_developer_key_to_build(self) -> None:
        """build() must receive the API key as developerKey."""
        with patch("mimesis.video_discovery.infra.youtube_api_client.build") as mock_build:
            mock_build.return_value = MagicMock()

            YouTubeApiClient(api_key="my-secret-key")

            _, kwargs = mock_build.call_args
            assert kwargs.get("developerKey") == "my-secret-key"

    def test_init_disables_discovery_cache(self) -> None:
        """build() must be called with cache_discovery=False."""
        with patch("mimesis.video_discovery.infra.youtube_api_client.build") as mock_build:
            mock_build.return_value = MagicMock()

            YouTubeApiClient(api_key="fake-api-key")

            _, kwargs = mock_build.call_args
            assert kwargs.get("cache_discovery") is False
