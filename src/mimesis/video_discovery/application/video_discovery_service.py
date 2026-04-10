"""Application service: VideoDiscoveryService.

Orchestrates a single keyword search run end-to-end:
  1. Create SearchJob (PENDING)
  2. Auto-paginate YouTube up to max_results
  3. Batch-enrich with full metadata (via YouTubeApiPort)
  4. Deduplicate against the global Discovery Ledger
  5. Emit VideoDiscovered events to Service Bus
  6. Return SearchJob (COMPLETED or FAILED)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from mimesis.video_discovery.domain.events import VideoDiscovered
from mimesis.video_discovery.domain.exceptions import QuotaExceededException
from mimesis.video_discovery.domain.models import SearchJob, SearchQuery
from mimesis.video_discovery.ports.discovery_ledger_port import DiscoveryLedgerPort
from mimesis.video_discovery.ports.event_publisher_port import EventPublisherPort
from mimesis.video_discovery.ports.youtube_api_port import YouTubeApiPort

logger = logging.getLogger(__name__)

# YouTube Data API v3 maximum per search.list call
_PAGE_SIZE = 50


class VideoDiscoveryService:
    """Use-case orchestrator for REQ-1 (search) and REQ-2 (event queueing)."""

    def __init__(
        self,
        youtube_api: YouTubeApiPort,
        ledger: DiscoveryLedgerPort,
        publisher: EventPublisherPort,
    ) -> None:
        self._youtube_api = youtube_api
        self._ledger = ledger
        self._publisher = publisher

    def run_search(self, query: SearchQuery, max_results: int) -> SearchJob:
        """Search YouTube for *query*, deduplicate, and emit VideoDiscovered events.

        Args:
            query:       Keyword and optional filters.
            max_results: Hard ceiling on total videos processed across all pages.

        Returns:
            The completed (or failed) ``SearchJob`` aggregate.
        """
        job = SearchJob.create(query=query, max_results=max_results)
        logger.info(
            "SearchJob started | job_id=%s keyword=%r max_results=%d",
            job.search_job_id,
            query.keyword,
            max_results,
        )

        job.mark_running()

        try:
            self._paginate_and_emit(job, query, max_results)
        except QuotaExceededException:
            logger.error(
                "YouTube quota exhausted — SearchJob failed | job_id=%s "
                "new_discoveries=%d duplicates_skipped=%d pages_fetched=%d",
                job.search_job_id,
                job.new_discoveries,
                job.duplicates_skipped,
                job.pages_fetched,
            )
            job.mark_failed()
            return job
        except Exception:
            logger.exception(
                "Unexpected error in run_search | job_id=%s", job.search_job_id
            )
            job.mark_failed()
            raise

        job.mark_completed()
        logger.info(
            "SearchJob completed | job_id=%s new=%d dupes=%d pages=%d",
            job.search_job_id,
            job.new_discoveries,
            job.duplicates_skipped,
            job.pages_fetched,
        )
        return job

    # ── private ──────────────────────────────────────────────────────────────

    def _paginate_and_emit(
        self,
        job: SearchJob,
        query: SearchQuery,
        max_results: int,
    ) -> None:
        """Inner pagination loop — separated so QuotaExceededException propagates cleanly."""
        page_token: str | None = None
        total_processed = 0

        while total_processed < max_results:
            remaining = max_results - total_processed
            page = self._youtube_api.search_page(
                query=query,
                page_size=min(_PAGE_SIZE, remaining),
                page_token=page_token,
            )
            job.record_page()

            if not page.video_metadatas:
                # Empty page — no more results from YouTube
                break

            for video_id, metadata in page.video_metadatas:
                if self._ledger.exists(video_id):
                    job.record_duplicate()
                    logger.debug("Duplicate skipped | video_id=%s", video_id)
                    continue

                self._ledger.record(video_id)

                event = VideoDiscovered(
                    search_job_id=job.search_job_id,
                    video_id=video_id,
                    metadata=metadata,
                    occurred_at=datetime.now(UTC),
                )
                self._publisher.publish(event)
                job.record_discovery()
                logger.debug("VideoDiscovered emitted | video_id=%s", video_id)

            total_processed += len(page.video_metadatas)

            if page.next_page_token is None:
                break  # YouTube has no more pages

            page_token = page.next_page_token
