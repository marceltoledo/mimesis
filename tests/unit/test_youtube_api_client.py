"""Unit tests for YouTubeApiClient — covers ADC regression (issues #25, #27).

These tests verify that YouTubeApiClient construction does NOT trigger
google.auth.default() (which fails in Azure where no Google ADC is present).

Root cause (issue #27): passing http=httplib2.Http() to build() is insufficient
because google-api-python-client calls _auth.default_credentials() inside
build_from_document() regardless of whether http is provided. The correct fix
is to pass credentials=AnonymousCredentials(), which prevents the ADC lookup.

The googleapiclient.discovery.build call is patched to avoid network I/O.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from google.auth.credentials import AnonymousCredentials

from mimesis.video_discovery.infra.youtube_api_client import YouTubeApiClient


class TestYouTubeApiClientInit:
    """Regression tests for issues #25 and #27 — missing Google ADC in Azure."""

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

    def test_init_passes_anonymous_credentials_to_build(self) -> None:
        """build() must receive AnonymousCredentials to bypass ADC lookup.

        Passing http= is insufficient in newer google-api-python-client versions;
        build_from_document() calls _auth.default_credentials() even when http is
        provided unless credentials are explicitly supplied.
        """
        with patch("mimesis.video_discovery.infra.youtube_api_client.build") as mock_build:
            mock_build.return_value = MagicMock()

            YouTubeApiClient(api_key="fake-api-key")

            _, kwargs = mock_build.call_args
            assert isinstance(kwargs.get("credentials"), AnonymousCredentials)

    def test_init_does_not_pass_http_to_build(self) -> None:
        """build() must NOT receive an http argument (would conflict with credentials)."""
        with patch("mimesis.video_discovery.infra.youtube_api_client.build") as mock_build:
            mock_build.return_value = MagicMock()

            YouTubeApiClient(api_key="fake-api-key")

            _, kwargs = mock_build.call_args
            assert "http" not in kwargs

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
