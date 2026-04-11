"""Runtime configuration for BC-02 Video Ingestion."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VideoIngestionConfig:
    storage_account_url: str
    ingestion_ledger_table: str
    service_bus_namespace: str
    video_ingested_queue: str
    app_insights_connection_string: str

    @classmethod
    def from_env(cls) -> VideoIngestionConfig:
        return cls(
            storage_account_url=_require("MIMESIS_STORAGE_ACCOUNT_URL").replace(
                ".table.", ".blob."
            ),
            ingestion_ledger_table=os.getenv("MIMESIS_INGESTION_LEDGER_TABLE", "ingestionLedger"),
            service_bus_namespace=_require("MIMESIS_SERVICE_BUS_NAMESPACE"),
            video_ingested_queue=os.getenv(
                "MIMESIS_SERVICE_BUS_INGESTED_QUEUE", "sb-queue-video-ingested"
            ),
            app_insights_connection_string=_require("MIMESIS_APP_INSIGHTS_CONNECTION_STRING"),
        )


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Required environment variable '{key}' is not set.")
    return value
