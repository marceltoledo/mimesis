"""Unit tests for domain models and aggregate invariants."""

from __future__ import annotations

import pytest

from mimesis.video_discovery.domain.models import (
    SearchFilters,
    SearchJob,
    SearchJobStatus,
    SearchQuery,
)


class TestSearchJobStateMachine:
    def test_new_job_is_pending_with_zero_counters(self) -> None:
        job = SearchJob.create(query=SearchQuery(keyword="test"), max_results=50)
        assert job.status == SearchJobStatus.PENDING
        assert job.new_discoveries == 0
        assert job.duplicates_skipped == 0
        assert job.pages_fetched == 0

    def test_mark_running_from_pending_succeeds(self) -> None:
        job = SearchJob.create(query=SearchQuery(keyword="test"), max_results=50)
        job.mark_running()
        assert job.status == SearchJobStatus.RUNNING

    def test_mark_completed_from_running_succeeds(self) -> None:
        job = SearchJob.create(query=SearchQuery(keyword="test"), max_results=50)
        job.mark_running()
        job.mark_completed()
        assert job.status == SearchJobStatus.COMPLETED

    def test_mark_failed_from_running_succeeds(self) -> None:
        job = SearchJob.create(query=SearchQuery(keyword="test"), max_results=50)
        job.mark_running()
        job.mark_failed()
        assert job.status == SearchJobStatus.FAILED

    def test_mark_failed_from_pending_succeeds(self) -> None:
        """mark_failed() must be callable from any state (unexpected early errors)."""
        job = SearchJob.create(query=SearchQuery(keyword="test"), max_results=50)
        job.mark_failed()
        assert job.status == SearchJobStatus.FAILED

    def test_cannot_mark_completed_from_pending(self) -> None:
        job = SearchJob.create(query=SearchQuery(keyword="test"), max_results=50)
        with pytest.raises(ValueError, match="RUNNING"):
            job.mark_completed()

    def test_cannot_mark_running_twice(self) -> None:
        job = SearchJob.create(query=SearchQuery(keyword="test"), max_results=50)
        job.mark_running()
        with pytest.raises(ValueError, match="PENDING"):
            job.mark_running()

    def test_counters_increment_correctly(self) -> None:
        job = SearchJob.create(query=SearchQuery(keyword="test"), max_results=50)
        job.mark_running()
        job.record_discovery()
        job.record_discovery()
        job.record_duplicate()
        job.record_page()
        job.record_page()

        assert job.new_discoveries == 2
        assert job.duplicates_skipped == 1
        assert job.pages_fetched == 2

    def test_search_job_id_is_uuid(self) -> None:
        from uuid import UUID

        job = SearchJob.create(query=SearchQuery(keyword="test"), max_results=50)
        assert isinstance(job.search_job_id, UUID)

    def test_two_jobs_have_different_ids(self) -> None:
        q = SearchQuery(keyword="x")
        j1 = SearchJob.create(query=q, max_results=10)
        j2 = SearchJob.create(query=q, max_results=10)
        assert j1.search_job_id != j2.search_job_id


class TestSearchQuery:
    def test_blank_keyword_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            SearchQuery(keyword="   ")

    def test_empty_keyword_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            SearchQuery(keyword="")

    def test_valid_keyword(self) -> None:
        q = SearchQuery(keyword="python tutorials")
        assert q.keyword == "python tutorials"

    def test_filters_are_optional(self) -> None:
        q = SearchQuery(keyword="test")
        assert q.filters is None


class TestSearchFilters:
    def test_valid_duration_short(self) -> None:
        f = SearchFilters(video_duration="short")
        assert f.video_duration == "short"

    def test_valid_duration_medium(self) -> None:
        f = SearchFilters(video_duration="medium")
        assert f.video_duration == "medium"

    def test_valid_duration_long(self) -> None:
        f = SearchFilters(video_duration="long")
        assert f.video_duration == "long"

    def test_invalid_duration_raises(self) -> None:
        with pytest.raises(ValueError, match="video_duration"):
            SearchFilters(video_duration="super_long")

    def test_all_fields_optional(self) -> None:
        f = SearchFilters()
        assert f.language is None
        assert f.published_after is None
        assert f.video_duration is None
        assert f.region_code is None

    def test_frozen_immutable(self) -> None:
        f = SearchFilters(language="en")
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            f.language = "pt"  # type: ignore[misc]
