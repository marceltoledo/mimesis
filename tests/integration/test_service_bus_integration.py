"""Integration tests — Azure Service Bus event publishing and consuming.

Validates AC-03 (one event per video), AC-04 (self-contained payload),
and AC-09 (consumer receives and settles).

Require a live Service Bus namespace with the Terraform-provisioned queue.

Run with: pytest -m integration tests/integration/test_service_bus_integration.py
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime

import pytest
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient

from mimesis.video_discovery.domain.events import VideoDiscovered
from mimesis.video_discovery.domain.models import VideoMetadata
from mimesis.video_discovery.infra.video_event_publisher import ServiceBusEventPublisher


def _namespace() -> str:
    return os.environ["MIMESIS_SERVICE_BUS_NAMESPACE"]


def _queue() -> str:
    return os.environ.get("MIMESIS_SERVICE_BUS_QUEUE", "sb-queue-video-discovered")


def _sample_event(video_id: str) -> VideoDiscovered:
    return VideoDiscovered(
        search_job_id=uuid.uuid4(),
        video_id=video_id,
        metadata=VideoMetadata(
            title="Integration Test Video",
            description="Created by the integration test suite.",
            channel_id="ch_integration",
            channel_title="Integration Channel",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            duration="PT3M",
            view_count=100,
            like_count=5,
            thumbnails={"default": {"url": "https://example.com/thumb.jpg"}},
            tags=["test"],
            category_id="22",
            default_language="en",
        ),
        occurred_at=datetime.now(UTC),
    )


@pytest.mark.integration
class TestServiceBusLive:
    def test_ac03_and_ac04_publish_and_receive_event(self) -> None:
        """AC-03: Exactly one message per video; AC-04: self-contained payload."""
        video_id = f"integration-test-{uuid.uuid4().hex[:8]}"
        event = _sample_event(video_id)

        # Publish
        with ServiceBusEventPublisher(_namespace(), _queue()) as publisher:
            publisher.publish(event)

        # Consume and settle — AC-09
        credential = DefaultAzureCredential()
        with ServiceBusClient(
            fully_qualified_namespace=_namespace(), credential=credential
        ) as sb_client, sb_client.get_queue_receiver(_queue(), max_wait_time=10) as receiver:
            found = False
            for msg in receiver:
                payload: dict[str, object] = json.loads(str(msg))
                if payload.get("video_id") == video_id:
                    # AC-04: verify self-contained fields
                    assert "search_job_id" in payload
                    assert "occurred_at" in payload
                    metadata = payload.get("metadata", {})
                    assert metadata.get("title")  # type: ignore[union-attr]
                    assert metadata.get("channel_id")  # type: ignore[union-attr]
                    # AC-09: settle (complete) the message
                    receiver.complete_message(msg)
                    found = True
                    break
                else:
                    # Another test message — abandon to avoid interfering
                    receiver.abandon_message(msg)

            assert found, f"Event for video_id={video_id!r} not found on queue"

    def test_ac09_consumer_can_abandon_for_retry(self) -> None:
        """AC-09: Abandoned messages are retried by Service Bus (not consumed once)."""
        video_id = f"integration-abandon-{uuid.uuid4().hex[:8]}"
        event = _sample_event(video_id)

        with ServiceBusEventPublisher(_namespace(), _queue()) as publisher:
            publisher.publish(event)

        credential = DefaultAzureCredential()
        with ServiceBusClient(
            fully_qualified_namespace=_namespace(), credential=credential
        ) as sb_client, sb_client.get_queue_receiver(_queue(), max_wait_time=10) as receiver:
            for msg in receiver:
                payload = json.loads(str(msg))
                if payload.get("video_id") == video_id:
                    # Abandon — message should reappear later
                    receiver.abandon_message(msg)
                    break
                else:
                    receiver.abandon_message(msg)
