"""Port interface for publishing VideoIngested events."""

from abc import ABC, abstractmethod

from mimesis.video_ingestion.domain.events import VideoIngested


class IngestedEventPublisherPort(ABC):
    @abstractmethod
    def publish(self, event: VideoIngested) -> None:
        """Publish a single VideoIngested event."""
