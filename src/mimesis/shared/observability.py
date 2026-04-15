"""Application Insights telemetry setup.

Call ``configure_observability()`` once at application startup.
All structured logging flows to Azure Monitor via OpenTelemetry.

The ``cloud_RoleName`` dimension (used to distinguish components in App Insights)
is set via the OTEL_SERVICE_NAME environment variable or the ``service_name``
parameter.
"""

from __future__ import annotations

import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor

logger = logging.getLogger(__name__)


def configure_observability(
    connection_string: str,
    service_name: str = "mimesis",
    build_id: str = "unknown",
) -> None:
    """Configure OpenTelemetry → Application Insights export.

    Args:
        connection_string: Application Insights connection string
                           (from Terraform output ``app_insights_connection_string``).
        service_name:      Sets ``cloud_RoleName`` in App Insights.
                           Defaults to 'mimesis'.
        build_id:          Deployment identity stamped on every span via
                           the ``build.id`` OTEL resource attribute.
                           Defaults to 'unknown'.
    """
    existing = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = f"{existing},build.id={build_id}".lstrip(",")
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    configure_azure_monitor(connection_string=connection_string)
    logger.info("Startup | service=%s build_id=%s", service_name, build_id)
