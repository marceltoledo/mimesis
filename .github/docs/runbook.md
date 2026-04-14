# Mimesis — Operations Runbook

## BC-01 Video Discovery — Function Key

### What is the Function Key?

BC-01 is an Azure Function HTTP trigger secured with `AuthLevel.FUNCTION`.
Every request must include the function host key in the `x-functions-key` header.

```
POST https://<function-app>.azurewebsites.net/api/video-discovery
x-functions-key: <host-key>
Content-Type: application/json

{"keyword": "Graham Stephan", "max_results": 15}
```

### How to retrieve the current host key

**Azure Portal**: Function App → App Keys → Host keys → `default`

**Azure CLI** (requires `Microsoft.Web/sites/host/default/listKeys/action`):

```bash
az rest \
  --method post \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/mimesis-dev-rg/providers/Microsoft.Web/sites/<app-name>/host/default/listKeys?api-version=2024-04-01" \
  --query "functionKeys.default" -o tsv
```

### Key rotation procedure

1. **Rotate** — In the Portal (App Keys) or via CLI, delete the `default` key and create a new one.
2. **Update secrets** — Update the GitHub repository secret `AZURE_BC01_FUNCTION_KEY` with the new key.
3. **Update any stored client** — Update any scripts or integrations that use the old key.
4. **Verify** — Trigger a smoke test: `POST /api/video-discovery` returns HTTP 200 with the new key.

Rotation should be done:
- Whenever a key may have been exposed (logs, error messages, screenshots)
- On team member offboarding
- Quarterly at minimum

---

## Observability

### Application Insights

Both BC-01 and BC-02 emit structured logs and request telemetry to the shared
Application Insights instance. Use the `cloud_RoleName` dimension to filter:

| Component | `cloud_RoleName` |
|---|---|
| BC-01 Video Discovery | `mimesis-video-discovery` |
| BC-02 Video Ingestion | `mimesis-video-ingestion` |

**Query — BC-01 failures in the last hour:**
```kusto
requests
| where timestamp > ago(1h)
| where cloud_RoleName == 'mimesis-video-discovery'
| where success == false
| project timestamp, resultCode, duration, operation_Id
| order by timestamp desc
```

**Query — BC-02 DLQ events:**
```kusto
AzureDiagnostics
| where Category == "OperationalLogs"
| where ResourceType == "NAMESPACES"
| where OperationName contains "DeadLetter"
| order by TimeGenerated desc
```

### Alerts summary

| Alert | Condition | Severity |
|---|---|---|
| `dlq-count-warning` | DLQ count ≥ 1 (avg, 15m window) | Warning |
| `dlq-count-critical` | DLQ count ≥ 5 (avg, 15m window) | Critical |
| `dlq-age-warning` | DLQ messages present continuously for 15m | Warning |
| `dlq-age-critical` | DLQ messages present continuously for 60m | Critical |
| `fn-failure-warning` | Function failure rate > 5% (15m) | Warning |
| `fn-failure-critical` | Function failure rate > 20% (15m) | Critical |

### DLQ triage procedure

1. Check Application Insights for exception details (query above).
2. Inspect the DLQ in Service Bus Explorer (Portal → Service Bus → Queue → Dead-letter).
3. Common causes:
   - **Invalid JSON payload** — `InvalidVideoDiscoveredEventError` in BC-02 logs.
   - **YouTube download failure** — `PytubefixMediaProcessor` raised `RuntimeError`.
   - **Blob storage error** — `ArtifactStoreError` in BC-02 logs.
4. Fix the root cause and re-submit messages from the DLQ if safe.

---

## Blob artifact naming convention

BC-02 writes artifacts to the following paths (date from the discovery event's `occurred_at`):

| Artifact | Path |
|---|---|
| Source video | `raw-videos/{yyyy}/{mm}/{dd}/{video_id}/source.mp4` |
| Extracted audio | `extracted-audio/{yyyy}/{mm}/{dd}/{video_id}/audio.mp3` |
| Ingestion metadata | `video-metadata/{yyyy}/{mm}/{dd}/{video_id}/metadata.json` |

Paths are deterministic: the same `video_id` + `occurred_at` always maps to the same blobs,
making Service Bus retries safe without creating duplicates.
