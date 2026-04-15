# Session: Terraform Provider Lock File Mismatch — Diagnosis & Fix

**Issue:** #22 — DEV-Rollout.yml run failed  
**Failed run:** https://github.com/marceltoledo/mimesis/actions/runs/24441604403  
**Fix PR:** #23  

---

## Problem

The **DEV Rollout** GitHub Actions workflow (`dev-rollout.yml`) was failing consistently at the `Terraform DEV (init → plan → apply)` job with **exit code 1** in under 30 seconds — before `terraform plan` even ran.

### Error message (from Actions logs)

```
Error: Failed to query available provider packages

Could not retrieve the list of available versions for provider
hashicorp/azurerm: locked provider registry.terraform.io/hashicorp/azurerm
3.117.1 does not match configured version constraint ~> 4.0; must use
terraform init -upgrade to allow selection of new versions
```

### Why the error occurred

Two compounding issues:

1. **`.terraform.lock.hcl` was listed in `.gitignore`** — the lock file was never committed to source control. Each CI run started with no lock file.

2. **Stale local lock file pinned the wrong major version** — the lock file on the developer's machine pinned `azurerm 3.117.1` (constraint `~> 3.100`), while `provider.tf` had been updated to require `~> 4.0`. The mismatch was invisible locally until CI ran `terraform init` without `-upgrade`.

### Files involved

| File | Problem |
|---|---|
| `infrastructure/terraform/.terraform.lock.hcl` | Pinned azurerm `3.117.1` / constraint `~> 3.100`; inconsistent with `provider.tf` |
| `infrastructure/terraform/provider.tf` | Declared `azurerm ~> 4.0` |
| `.gitignore` | Incorrectly excluded `.terraform.lock.hcl` from version control |

---

## Diagnosis Steps

1. Fetched the failing run URL from the issue body.
2. Scraped the Actions run page — identified failure in `Terraform DEV (init → plan → apply)`, 28s duration, exit code 1, downstream jobs skipped.
3. Checked git log to identify recent commits and the commit on the failed run (`c02f6cf`).
4. Ran `terraform init -backend-config=backend.hcl -reconfigure` locally → reproduced the exact error.
5. Inspected `.terraform.lock.hcl` — confirmed azurerm `3.117.1` with constraint `~> 3.100`.
6. Inspected `provider.tf` — confirmed constraint is `~> 4.0`.
7. Checked `.gitignore` — confirmed `.terraform.lock.hcl` was explicitly excluded.

---

## Resolution

### Step 1 — Remove lock file from `.gitignore`

```diff
- infrastructure/terraform/.terraform.lock.hcl
+ # .terraform.lock.hcl must be committed so CI uses pinned provider versions
```

The `.terraform/` directory (provider binaries, large) remains gitignored. Only the lock file exclusion was removed.

### Step 2 — Upgrade and commit the lock file

```bash
cd infrastructure/terraform
terraform init -upgrade -backend-config=backend.hcl
```

Result: lock file updated to `azurerm 4.68.0` (constraint `~> 4.0`) and `azapi 2.9.0`.

Validated with:
```bash
terraform validate
# Success! The configuration is valid (two deprecation warnings, not blockers)
```

### Step 3 — Commit on an issue branch, open PR

Changes committed to branch `issue/22-issues-in-the-dev-rollout-yml-run-failed`, PR #23 opened against `main`. Direct commits to `main` were reverted.

---

## Root Cause Pattern

> **Terraform lock file version drift** — when `provider.tf` major version is bumped but the developer runs `terraform init` without `-upgrade`, the local lock file is not updated. If the lock file is also gitignored, CI never sees a lock file and runs a fresh init that fails on the mismatch.

---

## Prevention Rules

1. **Always commit `.terraform.lock.hcl`** — it must be in source control. Only ignore `.terraform/` (the binary cache directory).
2. **After any provider version constraint change in `provider.tf`, run `terraform init -upgrade`** and commit the updated lock file in the same PR.
3. **`terraform validate` must pass before merging** any Terraform change.
4. **CI `terraform init` must not use `-upgrade`** — it should rely on the committed lock file. If it needs `-upgrade`, that is a signal the lock file was not updated locally first.

---

## Checklist for Future Terraform Provider Upgrades

- [ ] Update version constraint in `provider.tf`
- [ ] Run `terraform init -upgrade` locally
- [ ] Run `terraform validate` — confirm no errors (warnings acceptable)
- [ ] Commit `.terraform.lock.hcl` alongside the `provider.tf` change
- [ ] Open PR; do **not** push directly to `main`
