"""Integration tests — YouTube Data API v3.

These tests call the LIVE YouTube API and require:
  - MIMESIS_KEY_VAULT_URL set
  - A valid 'youtube-api-key' secret in the Key Vault
  - Managed Identity or az login available

Run with: pytest -m integration tests/integration/test_youtube_api_integration.py
"""

from __future__ import annotations

import os

import pytest

from mimesis.video_discovery.infra.secrets_provider import SecretsProvider
from mimesis.video_discovery.infra.youtube_api_client import YouTubeApiClient
from mimesis.video_discovery.domain.models import SearchQuery


def _get_client() -> YouTubeApiClient:
    vault_url = os.environ["MIMESIS_KEY_VAULT_URL"]
    api_key = SecretsProvider(vault_url).get_secret("youtube-api-key")
    return YouTubeApiClient(api_key=api_key)


@pytest.mark.integration
class TestYouTubeApiLive:
    def test_ac01_search_returns_full_metadata(self) -> None:
        """AC-01: A real search must return VideoMetadata with all required fields."""
        client = _get_client()
        page = client.search_page(
            query=SearchQuery(keyword="python tutorials"),
            page_size=3,
        )

        assert len(page.video_metadatas) > 0
        for video_id, meta in page.video_metadatas:
            assert video_id
            assert meta.title
            assert meta.channel_id
            assert meta.channel_title
            assert meta.published_at is not None
            assert meta.duration
            assert meta.view_count >= 0
            assert meta.thumbnails
            assert meta.category_id

    def test_search_with_all_filters_does_not_raise(self) -> None:
        """AC-08: Filters are forwarded to the API without errors."""
        from datetime import datetime, timezone

        from mimesis.video_discovery.domain.models import SearchFilters

        client = _get_client()
        page = client.search_page(
            query=SearchQuery(
                keyword="python",
                filters=SearchFilters(
                    language="en",
                    published_after=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    video_duration="short",
                    region_code="GB",
                ),
            ),
            page_size=5,
        )
        # No exception raised — result may be empty depending on quota / content
        assert page.video_metadatas is not None

    def test_pagination_returns_next_page_token_when_results_exist(self) -> None:
        """AC-07: nextPageToken is populated when YouTube has more results."""
        client = _get_client()
        page = client.search_page(
            query=SearchQuery(keyword="python tutorials"),
            page_size=50,
        )
        # For a popular keyword there should be more than one page
        # (may occasionally fail if quota is exhausted)
        if len(page.video_metadatas) == 50:
            assert page.next_page_token is not None
