"""Shared pytest fixtures for the Mimesis test suite."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mimesis.video_discovery.domain.models import (
    SearchFilters,
    SearchJob,
    SearchQuery,
    VideoMetadata,
)


@pytest.fixture
def sample_query() -> SearchQuery:
    return SearchQuery(keyword="python tutorials")


@pytest.fixture
def sample_query_with_filters() -> SearchQuery:
    return SearchQuery(
        keyword="storytelling",
        filters=SearchFilters(
            language="en",
            published_after=datetime(2024, 1, 1, tzinfo=UTC),
            video_duration="medium",
            region_code="GB",
        ),
    )


@pytest.fixture
def sample_metadata() -> VideoMetadata:
    return VideoMetadata(
        title="How to Master Python",
        description="A comprehensive Python tutorial.",
        channel_id="UC_test_channel",
        channel_title="Test Channel",
        published_at=datetime(2024, 6, 1, tzinfo=UTC),
        duration="PT10M30S",
        view_count=42_000,
        like_count=1_200,
        thumbnails={"default": {"url": "https://img.youtube.com/vi/vid1/default.jpg"}},
        tags=["python", "tutorial", "programming"],
        category_id="27",
        default_language="en",
    )


@pytest.fixture
def pending_job(sample_query: SearchQuery) -> SearchJob:
    return SearchJob.create(query=sample_query, max_results=50)
