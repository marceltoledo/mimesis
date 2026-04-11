"""Service Bus event publisher — concrete implementation of EventPublisherPort.

Sends VideoDiscovered events to the Azure Service Bus queue.
messageId is set to videoId to activate Service Bus built-in duplicate detection
as a secondary safety net (ADR-02).

Uses a long-lived sender for the duration of a SearchJob run for efficiency.
Call close() (or use as a context manager) after the job completes.
"""

from __future__ import annotations

import json
import logging

from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage

from mimesis.video_discovery.domain.events import VideoDiscovered
from mimesis.video_discovery.domain.exceptions import EventPublisherError
from mimesis.video_discovery.ports.event_publisher_port import EventPublisherPort

logger = logging.getLogger(__name__)


class ServiceBusEventPublisher(EventPublisherPort):
    """Publishes VideoDiscovered events to Azure Service Bus.

    Maintains a single open sender across multiple publish() calls within one
    SearchJob run to avoid per-message connection overhead.

    Usage::
        with ServiceBusEventPublisher(namespace, queue) as publisher:
            service.run_search(query, max_results)
    """

    def __init__(self, fully_qualified_namespace: str, queue_name: str) -> None:
        credential = DefaultAzureCredential()
        self._sb_client = ServiceBusClient(
            fully_qualified_namespace=fully_qualified_namespace,
            credential=credential,
        )
        self._sender = self._sb_client.get_queue_sender(queue_name=queue_name)

    def publish(self, event: VideoDiscovered) -> None:
        """Send a single VideoDiscovered event to the Service Bus queue."""
        body = json.dumps(event.to_dict(), ensure_ascii=False)
        message = ServiceBusMessage(
            body=body,
            message_id=event.video_id,  # Enables SB duplicate detection
            content_type="application/json",
        )
        try:
            self._sender.send_messages(message)
            logger.debug("VideoDiscovered sent to Service Bus | video_id=%s", event.video_id)
        except Exception as exc:
            raise EventPublisherError(
                f"Failed to publish VideoDiscovered for video_id={event.video_id!r}: {exc}"
            ) from exc

    def close(self) -> None:
        self._sender.close()
        self._sb_client.close()

    def __enter__(self) -> ServiceBusEventPublisher:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
