# Agent Knowledge Base

This document captures durable operational learnings for repository agents.

---

## GitHub Issue Creation via CLI

- Preferred command for long issue content:
  - `gh issue create --title "..." --body-file /tmp/issue.md`
- Keep issue content structured:
  - Solution summary
  - Acceptance criteria in GIVEN/WHEN/THEN
  - Technical design and ADRs
  - Implementation checklist

## Label Handling

- Repository labels are not guaranteed to exist.
- If `gh issue create` fails with `label not found`, retry without labels.
- Only create labels when explicitly requested.

---

## GitHub Actions

### Empty `env:` block
- GitHub Actions rejects a top-level `env:` key whose value contains **only comments** — YAML parses it as a null mapping, which GHA treats as an invalid value.
- **Always remove** unused `env:` blocks entirely. Do not leave comment-only stubs.
- Error signature: `(Line: N, Col: N): Unexpected value ''`

### Branch divergence
- When creating a feature branch from `main` while another open PR contains a critical fix, verify the fix is not missing from the new branch.
- If missing, cherry-pick or re-apply the fix on the new branch before opening the PR.

---

## Terraform

### Lock file management
- **`.terraform.lock.hcl` must be committed to source control.** Only the `.terraform/` directory (provider binaries) belongs in `.gitignore`.
- After any provider version constraint change in `provider.tf`, run `terraform init -upgrade` locally and commit the updated lock file in the same PR as the constraint change.
- CI `terraform init` must **not** use `-upgrade` — it relies on the committed lock file. If `-upgrade` is needed in CI that is a signal the local lock file was not refreshed first.
- `terraform validate` must pass (no errors; deprecation warnings are acceptable) before merging any Terraform change.

### Output audit after infra PRs
- After merging any infrastructure PR, grep `outputs.tf` for resource names referenced in `locals.tf` and confirm all deployment consumers are exported.
- Pattern: if a local is consumed by app deployment tooling (CI, scripts, downstream BC config), it must have a corresponding `output` block.

### Provider upgrade checklist
1. Update version constraint in `provider.tf`
2. Run `terraform init -upgrade` locally
3. Run `terraform validate` — confirm no errors
4. Commit `.terraform.lock.hcl` alongside the `provider.tf` change
5. Open PR; do **not** push directly to `main`

---

## Artifact Path Design

### Date-stable paths (idempotency across retries)
- Use the event's own timestamp (e.g. `occurred_at` from the `VideoDiscovered` payload) for date path segments — **never** `datetime.now()`.
- `datetime.now()` produces a different date on each Service Bus re-delivery, creating orphaned blobs and breaking idempotency.
- Pattern: `canonical_paths(video_id, occurred_at)` → `f"raw-videos/{occurred_at:%Y/%m/%d}/{video_id}/source.mp4"`

---

## Service Bus Monitoring

### DLQ age proxy metric
- Azure Monitor does not expose an "oldest DLQ message age" metric for Service Bus directly.
- **Proxy pattern**: use `DeadletteredMessages` with `Minimum` aggregation over the target window. If the minimum for the entire window is `> 0`, at least one DLQ message was present for the **whole** window — equivalent to "oldest message age > window size".
- Warning threshold: 15-minute window, `Minimum > 0`
- Critical threshold: 60-minute window, `Minimum > 0`
- Aggregation must be `Minimum`, not `Average` or `Total`.

---

## CI Recovery Workflow

### Standard loop for failing GitHub Actions checks

1. `gh pr checks <PR> --json name,state,link,workflow` — get check overview
2. `gh run view <RUN_ID> --job <JOB_ID> --log-failed` — pull failed logs
3. Reproduce failure locally with the **same command sequence used in CI**
4. Apply the minimal fix
5. Run local verification (see job-specific commands below)
6. Commit + push
7. Re-check PR statuses
8. Repeat until all required checks are green

### Terraform CI parity
```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

### Python CI parity
```bash
pip install -e ".[dev]"
ruff check src/ tests/
black --check src/ tests/
mypy src/
pytest -m "not integration" --cov=src/mimesis --cov-report=xml --cov-report=term-missing
```

### Safety constraints for CI recovery
- Never `git push --force` unless explicitly requested.
- Never discard unrelated local changes.
- Always assert the active repo path and branch before editing.

---

## Python Tooling

### Black formatting
- Use the project-pinned `.venv/bin/black` — never the system or global binary — to avoid version mismatches with CI.

### Config default alignment
- When a test fails for a config default value, check **both** the static default in the dataclass and the environment variable fallback. They must agree.

---

## Smoke Test Patterns

### BC-02 blob output verification
- After triggering BC-01, verify BC-02 has processed by polling the `raw-videos` container for up to 90 s.
- Use `az storage blob list --query "length(@)"` in a retry loop (e.g. 9 × 10 s).
- Issue a `::warning::` rather than failing hard when zero blobs are found — on first-ever runs the smoke keyword may not match any YouTube videos, so BC-02 never receives a message.
- Example:
  ```bash
  for i in $(seq 1 9); do
    count=$(az storage blob list --account-name "$AZURE_STORAGE_ACCOUNT" \
      --container-name raw-videos --auth-mode login \
      --query "length(@)" -o tsv 2>/dev/null || echo "0")
    [ "${count:-0}" -gt 0 ] && { found=1; break; }
    sleep 10
  done
  [ "${found:-0}" -eq 1 ] || echo "::warning::No blobs found after 90s."
  ```

---

## Flex Consumption (FC1) Deployment

### DO NOT use `az functionapp deploy --type zip`
- Returns **HTTP 502** from the Kudu SCM endpoint (`*.scm.azurewebsites.net/api/publish`) consistently on FC1 — server-side backend failure, not a network or auth issue. Retrying N times does not help.

### How FC1 resolves the runtime package at cold-start
1. Reads `kudu-state.json` from the deployment blob container.
2. Looks up `ActiveDeploymentId` → `Deployments[id].ResultPackagePath`.
3. If `ResultPackagePath` is **non-null** → mounts the local cached artifact at that path; **ignores `released-package.zip` in blob entirely** (no error, no log — silent).
4. If `ResultPackagePath` is **null** → downloads `released-package.zip` from blob (the fallback we want).

This means: uploading a new `released-package.zip` is silently ignored unless `kudu-state.json` is also updated.

### Correct deploy strategy — blob + kudu-state.json

```yaml
# 1. Upload pre-built zip
- name: Upload package to blob
  run: |
    az storage blob upload \
      --account-name "$STORAGE_ACCOUNT" \
      --container-name "$DEPLOY_CONTAINER" \
      --name released-package.zip \
      --file deploy.zip \
      --overwrite \
      --auth-mode key

# 2. Write new kudu-state.json (ResultPackagePath: null forces blob fallback)
- name: Update kudu-state.json
  run: |
    NEW_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
    cat > /tmp/kudu-state.json <<EOF
    {
      "ActiveDeploymentId": "$NEW_ID",
      "LatestDeploymentId": "$NEW_ID",
      "Deployments": {
        "$NEW_ID": {
          "Id": "$NEW_ID",
          "ResultPackagePath": null,
          "UploadedPackageName": "released-package.zip",
          "RemoteBuild": false,
          "Complete": true,
          "Status": 4
        }
      }
    }
    EOF
    az storage blob upload \
      --account-name "$STORAGE_ACCOUNT" \
      --container-name "$DEPLOY_CONTAINER" \
      --name kudu-state.json \
      --file /tmp/kudu-state.json \
      --overwrite \
      --auth-mode key

# 3. Restart + notify platform
- name: Restart and sync triggers
  run: |
    az functionapp restart --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP"
    az rest --method post \
      --url "https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP/syncfunctiontriggers?api-version=2022-03-01"
```

### Deployment blob containers (dev)

| Function App | Storage Account | Container |
|---|---|---|
| BC-01 `mimesis-dev-fd-fn` | `mimesisdevsa` | `fn-fd-deploy` |
| BC-02 `mimesis-dev-fi-fn` | `mimesisdevsa` | `fn-fi-deploy` |

Storage account naming convention: `<env-prefix>` from resource group (e.g. `mimesis-dev-rg` → strip `-rg` → strip `-` → append `sa` → `mimesisdevsa`).

### Auth
- CI SP with `Contributor` on the resource group can call `listKeys` on the storage account → use `--auth-mode key`.
- `Storage Blob Data Contributor` is **not** needed for the CI SP; that role is on the Managed Identity only.

---

## Build Identity (BUILD_ID) — Cross-Cutting Pattern

### Purpose
Allows operators to confirm in Application Insights logs which deployment version is running after a deploy — avoiding silent-no-op scenarios (issues #25, #27) where the function app cold-starts from a stale cached artifact and the new code is never executed.

### CI step ordering (must be respected)
1. Upload `released-package.zip` to blob
2. Write `kudu-state.json` (with new UUID and `ResultPackagePath: null`)
3. **Set `BUILD_ID` app setting** — must come after the zip is in place
4. Restart + syncfunctiontriggers

```bash
BUILD_ID="${GITHUB_SHA:0:8}-${GITHUB_RUN_NUMBER}"
az functionapp config appsettings set \
  --name "$APP" \
  --resource-group "$RG" \
  --settings "BUILD_ID=$BUILD_ID"
```

### Config pattern — every BC Config must include
```python
build_id: str = "unknown"  # in from_env(): os.getenv("BUILD_ID", "unknown")
```
Optional field — defaults to `"unknown"` so local dev and unit tests never need `BUILD_ID` set.

### Shared observability — `configure_observability()` signature
```python
def configure_observability(connection_string: str, service_name: str, build_id: str = "unknown") -> None:
    # Set BEFORE configure_azure_monitor() so it flows into every OTEL span
    existing = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = f"{existing},build.id={build_id}".lstrip(",")
    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)
    configure_azure_monitor(connection_string=connection_string)
    logger.info("Startup | service=%s build_id=%s", service_name, build_id)
```

### HTTP functions — must return `X-Build-Id` response header
- Capture `config.build_id` at cold-start (not per-request).
- Add `X-Build-Id: <build_id>` to every `func.HttpResponse`.
- Service Bus-triggered functions (BC-02, BC-03 …) have no HTTP surface — verify via App Insights logs only.

### Smoke test — BC-01 must assert `X-Build-Id` matches expected
```bash
build_id_header=$(curl -s -D - -o /dev/null -X POST ... | grep -i x-build-id | awk '{print $2}' | tr -d '\r')
if [ "$build_id_header" != "$EXPECTED_BUILD_ID" ]; then
  echo "FAILED: deployment identity mismatch. Expected=$EXPECTED_BUILD_ID Got=$build_id_header"
  exit 1
fi
```

### Build ID format
`${GITHUB_SHA:0:8}-${GITHUB_RUN_NUMBER}` — short SHA (8 chars) + sequential run number. Example: `a3f9c1b2-47`. Human-readable; traceable to exact commit.

---

## BC-02 Video Ingestion Decisions (April 2026)

- Input queue: `sb-queue-video-discovered`
- Output queue: `sb-queue-video-ingested`
- Audio format: MP3
- Metadata blob scope: ingestion-owned metadata only (not full `VideoDiscovered` envelope)
- Retry/DLQ: align with discovery flow policy
- Raw video retention: 30 days
- Library split:
  - BC-01 discovery/metadata: `google-api-python-client`
  - BC-02 media download: `pytubefix`
