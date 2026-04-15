"""Azure Functions HTTP trigger for BC-01 Video Discovery."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

import azure.functions as func

from mimesis.shared.observability import configure_observability
from mimesis.video_discovery.application.video_discovery_service import VideoDiscoveryService
from mimesis.video_discovery.config import VideoDiscoveryConfig
from mimesis.video_discovery.domain.models import SearchFilters, SearchQuery
from mimesis.video_discovery.infra.discovery_ledger import TableStorageDiscoveryLedger
from mimesis.video_discovery.infra.secrets_provider import SecretsProvider
from mimesis.video_discovery.infra.video_event_publisher import ServiceBusEventPublisher
from mimesis.video_discovery.infra.youtube_api_client import YouTubeApiClient

logger = logging.getLogger(__name__)

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.function_name(name="VideoDiscovery")
@app.route(route="video-discovery", methods=["POST"])
def video_discovery(req: func.HttpRequest) -> func.HttpResponse:
    """Run one discovery job and publish VideoDiscovered events."""
    config = VideoDiscoveryConfig.from_env()
    configure_observability(
        connection_string=config.app_insights_connection_string,
        service_name="mimesis-video-discovery",
        build_id=config.build_id,
    )
    try:
        payload = _read_json_body(req)
        query = _build_query(payload)
        max_results = _resolve_max_results(payload, config.default_max_results)

        secrets = SecretsProvider(config.key_vault_url)
        youtube_api_key = secrets.get_secret("youtube-api-key")

        publisher = ServiceBusEventPublisher(
            fully_qualified_namespace=config.service_bus_namespace,
            queue_name=config.service_bus_queue,
        )

        try:
            service = VideoDiscoveryService(
                youtube_api=YouTubeApiClient(youtube_api_key),
                ledger=TableStorageDiscoveryLedger(
                    account_url=config.storage_account_url,
                    table_name=config.discovery_ledger_table,
                ),
                publisher=publisher,
            )
            job = service.run_search(query=query, max_results=max_results)
        finally:
            publisher.close()

        status_code = 200 if job.status.value == "COMPLETED" else 500
        body = {
            "search_job_id": str(job.search_job_id),
            "status": job.status.value,
            "keyword": query.keyword,
            "max_results": job.max_results,
            "new_discoveries": job.new_discoveries,
            "duplicates_skipped": job.duplicates_skipped,
            "pages_fetched": job.pages_fetched,
        }
        return func.HttpResponse(
            body=json.dumps(body),
            status_code=status_code,
            mimetype="application/json",
            headers={"X-Build-Id": config.build_id},
        )
    except ValueError as exc:
        return func.HttpResponse(
            body=json.dumps({"error": str(exc)}),
            status_code=400,
            mimetype="application/json",
            headers={"X-Build-Id": config.build_id},
        )
    except Exception:
        logger.exception("VideoDiscovery function failed")
        return func.HttpResponse(
            body=json.dumps({"error": "internal_server_error"}),
            status_code=500,
            mimetype="application/json",
            headers={"X-Build-Id": config.build_id},
        )


def _read_json_body(req: func.HttpRequest) -> dict[str, Any]:
    try:
        body = req.get_json()
    except ValueError as exc:
        raise ValueError("Request body must be valid JSON.") from exc

    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")
    return body


def _build_query(payload: dict[str, Any]) -> SearchQuery:
    keyword = payload.get("keyword")
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("Field 'keyword' is required and must be a non-empty string.")

    filters_payload = payload.get("filters")
    filters: SearchFilters | None = None
    if filters_payload is not None:
        if not isinstance(filters_payload, dict):
            raise ValueError("Field 'filters' must be an object when provided.")

        published_after_raw = filters_payload.get("published_after")
        published_after = None
        if isinstance(published_after_raw, str) and published_after_raw:
            published_after = datetime.fromisoformat(published_after_raw.replace("Z", "+00:00"))

        filters = SearchFilters(
            language=_as_optional_str(filters_payload.get("language")),
            published_after=published_after,
            video_duration=_as_optional_str(filters_payload.get("video_duration")),
            region_code=_as_optional_str(filters_payload.get("region_code")),
        )

    return SearchQuery(keyword=keyword.strip(), filters=filters)


def _resolve_max_results(payload: dict[str, Any], default_value: int) -> int:
    raw_value = payload.get("max_results")
    if raw_value is None:
        return default_value

    if not isinstance(raw_value, int):
        raise ValueError("Field 'max_results' must be an integer when provided.")
    if raw_value <= 0:
        raise ValueError("Field 'max_results' must be greater than zero.")
    return raw_value


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Filter values must be strings when provided.")
    stripped = value.strip()
    return stripped or None
