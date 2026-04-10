"""Port interface: domain event publisher."""

from abc import ABC, abstractmethod

from mimesis.video_discovery.domain.events import VideoDiscovered


class EventPublisherPort(ABC):
    """Contract for publishing ``VideoDiscovered`` domain events.

    Backed by Azure Service Bus (queue: ``sb-queue-video-discovered``).
    The ``messageId`` is set to ``videoId`` to leverage Service Bus
    built-in duplicate detection as a secondary safety net.
    """

    @abstractmethod
    def publish(self, event: VideoDiscovered) -> None:
        """Publish a single ``VideoDiscovered`` event.

        Raises:
            EventPublisherError: When the message cannot be sent to Service Bus.
        """
