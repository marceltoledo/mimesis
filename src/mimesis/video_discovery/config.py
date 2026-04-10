"""Runtime configuration for the Video Discovery bounded context.

Values are sourced from environment variables set by the compute host
(Azure Function / Container App / local shell).  There are no defaults for
security-sensitive settings — missing variables raise at startup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VideoDiscoveryConfig:
    """All runtime settings needed to run VideoDiscoveryService."""

    key_vault_url: str
    """Azure Key Vault URI, e.g. https://<name>.vault.azure.net/"""

    storage_account_url: str
    """Primary table endpoint of the Storage Account, e.g. https://<name>.table.core.windows.net/"""

    discovery_ledger_table: str
    """Azure Table name for the Discovery Ledger (provisioned by Terraform)."""

    service_bus_namespace: str
    """Fully-qualified Service Bus hostname, e.g. <name>.servicebus.windows.net"""

    service_bus_queue: str
    """Service Bus queue name for VideoDiscovered events."""

    app_insights_connection_string: str
    """Application Insights connection string for telemetry."""

    default_max_results: int = 500
    """Default ceiling for paginated searches when callers omit max_results."""

    @classmethod
    def from_env(cls) -> VideoDiscoveryConfig:
        """Build config from environment variables.  Raises RuntimeError for missing values."""
        return cls(
            key_vault_url=_require("MIMESIS_KEY_VAULT_URL"),
            storage_account_url=_require("MIMESIS_STORAGE_ACCOUNT_URL"),
            discovery_ledger_table=os.getenv(
                "MIMESIS_DISCOVERY_LEDGER_TABLE", "discoveryLedger"
            ),
            service_bus_namespace=_require("MIMESIS_SERVICE_BUS_NAMESPACE"),
            service_bus_queue=os.getenv(
                "MIMESIS_SERVICE_BUS_QUEUE", "sb-queue-video-discovered"
            ),
            app_insights_connection_string=_require(
                "MIMESIS_APP_INSIGHTS_CONNECTION_STRING"
            ),
            default_max_results=int(os.getenv("MIMESIS_DEFAULT_MAX_RESULTS", "500")),
        )


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(
            f"Required environment variable '{key}' is not set. "
            "See .env.example for the full list of required variables."
        )
    return value
