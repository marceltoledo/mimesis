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
