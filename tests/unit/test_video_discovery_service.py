"""Unit tests for VideoDiscoveryService — covers AC-01 through AC-09.

All Azure dependencies are replaced with in-memory fakes so these tests
are fast, fully isolated, and require no network access.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mimesis.video_discovery.application.video_discovery_service import (
    VideoDiscoveryService,
)
from mimesis.video_discovery.domain.models import (
    SearchFilters,
    SearchJobStatus,
    SearchQuery,
)
from tests.unit.fakes.fake_discovery_ledger import FakeDiscoveryLedger
from tests.unit.fakes.fake_event_publisher import FakeEventPublisher
from tests.unit.fakes.fake_youtube_api import FakeYouTubeApi

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_service(
    pages: list[list[str]],
    preexisting: set[str] | None = None,
    fail_on_page: int | None = None,
) -> tuple[VideoDiscoveryService, FakeYouTubeApi, FakeDiscoveryLedger, FakeEventPublisher]:
    youtube = FakeYouTubeApi(pages=pages, fail_on_page=fail_on_page)
    ledger = FakeDiscoveryLedger(preexisting=preexisting or set())
    publisher = FakeEventPublisher()
    service = VideoDiscoveryService(youtube_api=youtube, ledger=ledger, publisher=publisher)
    return service, youtube, ledger, publisher


# ── AC-01: keyword search returns videos with full metadata ───────────────────


class TestAC01FullMetadata:
    def test_single_result_has_all_required_metadata_fields(
        self, sample_query: SearchQuery
    ) -> None:
        service, _, _, publisher = _make_service(pages=[["vid1"]])
        job = service.run_search(query=sample_query, max_results=50)

        assert job.status == SearchJobStatus.COMPLETED
        assert len(publisher.published) == 1

        meta = publisher.published[0].metadata
        assert meta.title
        assert meta.description is not None
        assert meta.channel_id
        assert meta.channel_title
        assert meta.published_at is not None
        assert meta.duration
        assert meta.view_count >= 0
        assert meta.thumbnails
        assert meta.category_id

    def test_event_links_back_to_the_search_job(self, sample_query: SearchQuery) -> None:
        service, _, _, publisher = _make_service(pages=[["vid1"]])
        job = service.run_search(query=sample_query, max_results=50)

        assert publisher.published[0].search_job_id == job.search_job_id


# ── AC-02: empty search returns no results and no events ─────────────────────


class TestAC02EmptySearch:
    def test_empty_page_yields_zero_discoveries_and_no_events(
        self, sample_query: SearchQuery
    ) -> None:
        service, _, _, publisher = _make_service(pages=[[]])
        job = service.run_search(query=sample_query, max_results=50)

        assert job.status == SearchJobStatus.COMPLETED
        assert job.new_discoveries == 0
        assert len(publisher.published) == 0

    def test_empty_page_does_not_write_to_ledger(self, sample_query: SearchQuery) -> None:
        service, _, ledger, _ = _make_service(pages=[[]])
        service.run_search(query=sample_query, max_results=50)

        assert ledger.recorded == []


# ── AC-03: exactly one event per newly discovered video ───────────────────────


class TestAC03OneEventPerVideo:
    def test_n_new_videos_produce_exactly_n_events(self, sample_query: SearchQuery) -> None:
        video_ids = ["vid1", "vid2", "vid3"]
        service, _, _, publisher = _make_service(pages=[video_ids])
        job = service.run_search(query=sample_query, max_results=50)

        assert job.new_discoveries == 3
        assert len(publisher.published) == 3

    def test_published_events_cover_exactly_the_discovered_ids(
        self, sample_query: SearchQuery
    ) -> None:
        video_ids = ["vid1", "vid2", "vid3"]
        service, _, _, publisher = _make_service(pages=[video_ids])
        service.run_search(query=sample_query, max_results=50)

        published_ids = {e.video_id for e in publisher.published}
        assert published_ids == set(video_ids)


# ── AC-04: event payload is self-contained ────────────────────────────────────


class TestAC04SelfContainedPayload:
    def test_to_dict_contains_required_top_level_keys(self, sample_query: SearchQuery) -> None:
        service, _, _, publisher = _make_service(pages=[["vid1"]])
        service.run_search(query=sample_query, max_results=50)

        payload = publisher.published[0].to_dict()
        assert "search_job_id" in payload
        assert "video_id" in payload
        assert "occurred_at" in payload
        assert "metadata" in payload

    def test_to_dict_metadata_contains_required_fields(self, sample_query: SearchQuery) -> None:
        service, _, _, publisher = _make_service(pages=[["vid1"]])
        service.run_search(query=sample_query, max_results=50)

        metadata = publisher.published[0].to_dict()["metadata"]
        required_keys = {
            "title",
            "description",
            "channel_id",
            "channel_title",
            "published_at",
            "duration",
            "view_count",
            "thumbnails",
            "category_id",
        }
        assert required_keys.issubset(metadata.keys())  # type: ignore[union-attr]

    def test_search_job_id_is_serialised_as_string(self, sample_query: SearchQuery) -> None:
        service, _, _, publisher = _make_service(pages=[["vid1"]])
        service.run_search(query=sample_query, max_results=50)

        payload = publisher.published[0].to_dict()
        assert isinstance(payload["search_job_id"], str)


# ── AC-05: quota exhaustion is handled gracefully ─────────────────────────────


class TestAC05QuotaExhaustion:
    def test_quota_on_first_page_marks_job_failed(self, sample_query: SearchQuery) -> None:
        service, _, _, publisher = _make_service(pages=[[]], fail_on_page=0)
        job = service.run_search(query=sample_query, max_results=50)

        assert job.status == SearchJobStatus.FAILED
        assert len(publisher.published) == 0

    def test_quota_mid_run_stops_new_events_but_job_is_failed(
        self, sample_query: SearchQuery
    ) -> None:
        """Page 0 succeeds (10 events emitted), page 1 raises quota — job=FAILED."""
        service, _, _, publisher = _make_service(
            # Two pages: page 0 has 10 videos, page 1 raises quota
            pages=[[f"vid{i}" for i in range(10)], []],
            fail_on_page=1,
        )
        job = service.run_search(query=sample_query, max_results=200)

        assert job.status == SearchJobStatus.FAILED
        # Events from page 0 are already on the queue and must NOT be retracted
        assert len(publisher.published) == 10

    def test_quota_does_not_raise_to_caller(self, sample_query: SearchQuery) -> None:
        """run_search must not propagate QuotaExceededException — it swallows it."""
        service, _, _, _ = _make_service(pages=[[]], fail_on_page=0)
        job = service.run_search(query=sample_query, max_results=50)  # must not raise
        assert job.status == SearchJobStatus.FAILED


# ── AC-06: global deduplication prevents duplicate events ─────────────────────


class TestAC06GlobalDeduplication:
    def test_known_video_is_skipped_and_counter_incremented(
        self, sample_query: SearchQuery
    ) -> None:
        service, _, _, publisher = _make_service(pages=[["vid1", "vid2"]], preexisting={"vid1"})
        job = service.run_search(query=sample_query, max_results=50)

        assert job.duplicates_skipped == 1
        assert job.new_discoveries == 1
        assert not any(e.video_id == "vid1" for e in publisher.published)
        assert any(e.video_id == "vid2" for e in publisher.published)

    def test_known_video_is_not_re_recorded_in_ledger(self, sample_query: SearchQuery) -> None:
        service, _, ledger, _ = _make_service(pages=[["vid1"]], preexisting={"vid1"})
        service.run_search(query=sample_query, max_results=50)

        assert "vid1" not in ledger.recorded  # recorded = NEW writes only

    def test_all_videos_known_yields_zero_discoveries(self, sample_query: SearchQuery) -> None:
        all_known = {"vid1", "vid2", "vid3"}
        service, _, _, publisher = _make_service(pages=[list(all_known)], preexisting=all_known)
        job = service.run_search(query=sample_query, max_results=50)

        assert job.new_discoveries == 0
        assert job.duplicates_skipped == 3
        assert publisher.published == []

    def test_video_discovered_in_run_is_not_re_emitted_in_same_run(
        self, sample_query: SearchQuery
    ) -> None:
        """Same videoId appearing on two different pages → emitted only once."""
        service, _, _, publisher = _make_service(pages=[["vid1", "vid2"], ["vid1", "vid3"]])
        job = service.run_search(query=sample_query, max_results=200)

        published_ids = [e.video_id for e in publisher.published]
        assert published_ids.count("vid1") == 1
        assert job.new_discoveries == 3  # vid1, vid2, vid3


# ── AC-07: pagination fetches all results up to ceiling ───────────────────────


class TestAC07Pagination:
    def test_single_page_with_no_next_token_stops_after_one_page(
        self, sample_query: SearchQuery
    ) -> None:
        service, youtube, _, _ = _make_service(pages=[["vid1", "vid2"]])
        job = service.run_search(query=sample_query, max_results=1000)

        assert job.pages_fetched == 1
        assert job.new_discoveries == 2

    def test_multi_page_all_pages_followed_when_under_ceiling(
        self, sample_query: SearchQuery
    ) -> None:
        """3 pages of 10 each, max_results=200 → all 3 pages fetched."""
        pages = [[f"vid_{p}_{i}" for i in range(10)] for p in range(3)]
        service, youtube, _, publisher = _make_service(pages=pages)
        job = service.run_search(query=sample_query, max_results=200)

        assert job.pages_fetched == 3
        assert job.new_discoveries == 30

    def test_ceiling_stops_pagination_before_all_pages(self, sample_query: SearchQuery) -> None:
        """max_results=10, page has 10 videos → loop exits after page 0."""
        pages = [
            [f"vid_p0_{i}" for i in range(10)],  # page 0 → 10 results
            [f"vid_p1_{i}" for i in range(10)],  # page 1 → should not be fetched
        ]
        service, youtube, _, publisher = _make_service(pages=pages)
        job = service.run_search(query=sample_query, max_results=10)

        assert job.pages_fetched == 1
        assert job.new_discoveries == 10

    def test_ceiling_limits_results_on_partial_page(self, sample_query: SearchQuery) -> None:
        """max_results=5 with a page of 10: page_size hint = 5, fake returns 5."""
        service, youtube, _, publisher = _make_service(pages=[[f"vid{i}" for i in range(10)]])
        job = service.run_search(query=sample_query, max_results=5)

        # First call passes page_size=min(50, 5)=5 → fake returns 5 videos
        assert youtube.calls[0]["page_size"] == 5
        assert job.new_discoveries == 5


# ── AC-08: optional search filters are applied ────────────────────────────────


class TestAC08SearchFilters:
    def test_filters_are_forwarded_to_youtube_api(self) -> None:
        filters = SearchFilters(
            language="pt",
            published_after=datetime(2024, 1, 1, tzinfo=UTC),
            video_duration="long",
            region_code="BR",
        )
        query = SearchQuery(keyword="storytelling", filters=filters)
        service, youtube, _, _ = _make_service(pages=[["vid1"]])
        service.run_search(query=query, max_results=50)

        assert len(youtube.calls) >= 1
        forwarded_query = youtube.calls[0]["query"]
        assert forwarded_query.filters is not None
        assert forwarded_query.filters.language == "pt"
        assert forwarded_query.filters.video_duration == "long"
        assert forwarded_query.filters.region_code == "BR"
        assert forwarded_query.filters.published_after == datetime(2024, 1, 1, tzinfo=UTC)

    def test_no_filters_still_produces_results(self, sample_query: SearchQuery) -> None:
        """Baseline: search without filters works normally."""
        service, _, _, publisher = _make_service(pages=[["vid1", "vid2"]])
        job = service.run_search(query=sample_query, max_results=50)

        assert job.status == SearchJobStatus.COMPLETED
        assert len(publisher.published) == 2


# ── AC-09 (consumer settlement) is verified via integration tests ─────────────
# See tests/integration/test_service_bus_integration.py
