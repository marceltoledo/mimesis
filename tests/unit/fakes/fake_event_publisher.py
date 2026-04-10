"""In-memory fake implementation of EventPublisherPort for unit tests."""

from __future__ import annotations

from mimesis.video_discovery.domain.events import VideoDiscovered
from mimesis.video_discovery.ports.event_publisher_port import EventPublisherPort


class FakeEventPublisher(EventPublisherPort):
    """Captures published events in memory for assertion in unit tests."""

    def __init__(self) -> None:
        self.published: list[VideoDiscovered] = []
        """All events that were passed to publish(), in order."""

    def publish(self, event: VideoDiscovered) -> None:
        self.published.append(event)
