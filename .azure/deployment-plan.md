# Deployment Plan: DEV Rollout Parent (#5) Re-baseline

Status: Ready for Validation

## Why this re-baseline

Main branch changed significantly after the initial plan and now contains BC-01 and BC-02 implementation work. Also, issue branches for #5, #6, and #7 currently point to the same commit as main, so separate PR scope is no longer represented by branch diff.

## Current State Snapshot

1. Implemented in main:
   - BC-01 default max results now 15.
   - BC-01 and BC-02 Function Apps + related Terraform resources.
   - BC-02 ingestion application code and tests.
   - DEV workflows: rollout and smoke workflows exist.
2. Gap discovered against issue requirements:
   - Dev-rollout workflow failed at Azure login due missing client/tenant/subscription inputs.
   - No explicit oldest-DLQ-age warning/critical alerts found yet (only DLQ count + failure-rate alerts).
3. Branch topology issue:
   - `5-dev-rollout-bc-01-video-discovery-bc-02-video-ingestion`,
     `6-dev-rollout-track-1-infra-and-platform-baseline`, and
     `7-dev-rollout-track-2-app-hosts-and-end-to-end-validation`
     are all aligned with main and require re-scoping by new incremental commits.

## Parent/Child PR Strategy (Required)

Issue #5 remains parent tracking only. Delivery should be split into two child PRs:

1. Issue #6 PR (Track 1: Infra + platform baseline)
   - Workflow hardening for Azure OIDC input resolution and preflight checks.
   - Terraform/platform verification and any missing infra outputs needed by deployment automation.
   - Alerting parity checks for agreed DEV thresholds.

2. Issue #7 PR (Track 2: App hosts + e2e validation)
   - Function host packaging/deploy robustness.
   - End-to-end smoke validation and runbook updates.
   - Validation proof capture for BC-01 -> Service Bus -> BC-02 -> Blob path.

3. Issue #5 PR (parent)
   - Tracking-only updates: checklist synchronization, rollout readiness summary, and final closeout after #6 and #7 are merged and validated.

## Adjusted Execution Order

1. Stabilize deployment workflow credentials and required inputs (Issue #6).
2. Re-run DEV rollout infra/app deployment in GitHub Actions and capture evidence (Issue #6).
3. Validate app-level end-to-end smoke and artifact/alert behavior (Issue #7).
4. Update parent issue #5 with final readiness and close only after both child issues are complete.

## Validation Steps (for re-baselined rollout)

1. Workflow preflight:
   - verify Azure login inputs resolve from repository secrets/variables.
   - verify expected deploy inputs are present before deployment steps execute.
2. Infra validation:
   - `terraform fmt -check -recursive`
   - `terraform validate`
   - `terraform plan -var-file=dev.tfvars`
3. App validation:
   - `ruff check src tests`
   - `mypy src`
   - `black --check src tests`
   - `pytest -q`
4. Runtime smoke:
   - invoke BC-01 with Function Key and omitted `max_results`.
   - confirm event published to `sb-queue-video-discovered`.
   - confirm BC-02 artifact outputs in approved blob path convention.
5. Alerting checks:
   - validate DLQ count and failure-rate alerts are present.
   - track oldest-DLQ-age alerts as explicit gap if absent.

## Risks and Mitigations

1. Risk: credentials not available as repository secrets in workflow context.
   - Mitigation: support repository variables fallback and add explicit preflight validation.
2. Risk: split-PR structure not represented by current branch divergence.
   - Mitigation: apply new focused commits per child branch and avoid cross-track changes.
3. Risk: alert requirements drift from code.
   - Mitigation: include alert matrix check in Track 1 acceptance validation.