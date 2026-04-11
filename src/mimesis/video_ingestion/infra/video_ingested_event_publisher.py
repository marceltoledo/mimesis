"""Service Bus publisher for VideoIngested events."""

from __future__ import annotations

import json

from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage

from mimesis.video_ingestion.domain.events import VideoIngested
from mimesis.video_ingestion.domain.exceptions import IngestedEventPublisherError
from mimesis.video_ingestion.ports.ingested_event_publisher_port import IngestedEventPublisherPort


class ServiceBusVideoIngestedPublisher(IngestedEventPublisherPort):
    def __init__(self, fully_qualified_namespace: str, queue_name: str) -> None:
        credential = DefaultAzureCredential()
        self._client = ServiceBusClient(
            fully_qualified_namespace=fully_qualified_namespace,
            credential=credential,
        )
        self._sender = self._client.get_queue_sender(queue_name=queue_name)

    def publish(self, event: VideoIngested) -> None:
        body = json.dumps(event.to_dict(), ensure_ascii=False)
        message = ServiceBusMessage(
            body=body,
            content_type="application/json",
            message_id=event.video_id,
        )
        try:
            self._sender.send_messages(message)
        except Exception as exc:
            raise IngestedEventPublisherError(
                f"Failed to publish VideoIngested for '{event.video_id}': {exc}"
            ) from exc

    def close(self) -> None:
        self._sender.close()
        self._client.close()

    def __enter__(self) -> ServiceBusVideoIngestedPublisher:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
