# Deployment Plan: BC-01 Video Discovery + BC-02 Video Ingestion DEV Rollout

Status: Awaiting Approval

## Context

- Workspace mode: MODIFY existing Python project and existing Terraform stack.
- Environment target: `dev`
- Region: `northeurope`
- IaC: Terraform only
- Auth: Managed Identity with `DefaultAzureCredential`
- Messaging: Azure Service Bus queue `sb-queue-video-discovered`
- Storage: existing project storage account, LRS only
- Monitoring: existing shared Application Insights

## Current State

- BC-01 domain, ports, and Azure adapters already exist in `src/mimesis/video_discovery`.
- Shared Azure resources already exist in Terraform: Resource Group, user-assigned managed identity, Key Vault, Storage Account, Table Storage, Service Bus namespace/queue, Log Analytics Workspace, Application Insights.
- No Azure Functions host exists yet for BC-01 or BC-02.
- BC-02 application code does not exist in the repo; only architecture notes mention the notebook prototype.
- CI currently covers lint, typing, and unit tests only.

## Requirements Mapped From Issue

1. Change BC-01 `default_max_results` from `500` to `15`.
2. Add DEV compute for two Python Azure Function Apps on Linux Flex Consumption.
3. Reuse existing Storage Account, Service Bus, Key Vault, App Insights, and managed identity.
4. Implement BC-01 HTTP trigger secured with Function Key.
5. Implement BC-02 Service Bus trigger to download source media, extract audio, and write blob artifacts.
6. Apply approved blob naming convention:
   - `audio/{yyyy}/{mm}/{dd}/{video_id}/source.mp4`
   - `audio/{yyyy}/{mm}/{dd}/{video_id}/audio.mp3`
   - `audio/{yyyy}/{mm}/{dd}/{video_id}/metadata.json`
7. Configure DEV retry / DLQ thresholds and Application Insights alerting.
8. Add hybrid rollout automation: local-first bootstrap plus GitHub Actions for infra, app deploy, and smoke checks.

## Planned Architecture

### BC-01 Function App

- New Python Azure Functions host using Functions host v4 and Python programming model v2.
- One HTTP-triggered function with auth level `function`.
- Request body will map to `SearchQuery` and optional `max_results`.
- If `max_results` is omitted, the function will use config default `15`.
- Function startup will compose existing BC-01 adapters:
  - `SecretsProvider`
  - `YouTubeApiClient`
  - `TableStorageDiscoveryLedger`
  - `ServiceBusEventPublisher`
  - `VideoDiscoveryService`
- Telemetry will use existing `configure_observability()` with a BC-01-specific role name.

### BC-02 Function App

- New Python Azure Functions host using Functions host v4 and Python programming model v2.
- One Service Bus queue trigger bound to `sb-queue-video-discovered`.
- Function will deserialize `VideoDiscovered` event payload and construct the YouTube watch URL from `video_id`.
- Implementation will download the source video with `pytubefix`, extract MP3 audio through `ffmpeg`/`pydub`, and upload all artifacts to the existing Storage Account Blob service.
- Metadata blob will persist the event payload plus artifact paths and processing timestamps.
- Telemetry will use existing shared Application Insights with a BC-02-specific role name.

## Planned Terraform Changes

1. Extend `infrastructure/terraform/main.tf` with:
   - Azure Storage container for ingestion artifacts
   - Azure Functions Flex Consumption resources for BC-01 and BC-02
   - Function App settings for shared runtime configuration
   - Monitor action group and scheduled query alerts for failures and DLQ conditions
2. Extend `infrastructure/terraform/rbac.tf` with managed identity access for:
   - Blob Data Contributor on the Storage Account
   - Service Bus Data Receiver on the namespace for BC-02
3. Extend `infrastructure/terraform/outputs.tf` with:
   - BC-01 Function endpoint base URL
   - BC-01 function app name
   - BC-02 function app name
   - deployment-oriented outputs needed by scripts/workflows
4. Reduce queue `max_delivery_count` from `10` to `5` for DEV.

## Planned Application Changes

1. Update BC-01 config default and env fallback to `15`.
2. Add new package structure for Azure Function hosts and shared composition utilities.
3. Add BC-02 ingestion bounded-context code for:
   - config
   - event parsing model
   - downloader / audio extraction / blob upload adapters
   - application service orchestration
4. Add unit tests for:
   - BC-01 function request handling
   - BC-01 default max results behavior
   - BC-02 artifact path generation and metadata payloads
   - BC-02 duplicate/retry-safe processing boundaries where feasible without live Azure
5. Add documentation for local bootstrap and smoke checks.

## Planned Delivery Workflow

1. Local bootstrap:
   - install dependencies
   - run unit tests
   - validate Terraform formatting and configuration
   - smoke test function entrypoints locally where feasible
2. GitHub Actions:
   - infra validation / plan workflow
   - app package and deploy workflow for BC-01 and BC-02
   - post-deploy smoke workflow for BC-01 endpoint and blob artifact checks

## Risks / Assumptions

- BC-02 prototype notebook is not present in the repo, so ingestion implementation will be recreated from issue requirements and architecture notes.
- Local BC-02 execution depends on `ffmpeg` being available on the host running the function.
- Azure Functions Flex Consumption support in Terraform must be modeled with the provider resources available in the currently pinned `azurerm` version.
- Alerting for DLQ age/count will use Azure Monitor scheduled query alerts against Service Bus diagnostics / metrics available to the deployed namespace.

## Validation Plan

1. Run unit tests and lint/type checks.
2. Verify BC-01 omitted `max_results` resolves to `15`.
3. Verify event publication remains deduplicated for already-recorded videos.
4. Verify BC-02 artifact naming matches the approved convention.
5. Validate Terraform for DEV resources and outputs.
6. If local tools are available, run targeted smoke checks for HTTP request handling and message payload ingestion.

## Execution Order

1. Update Python dependencies and config defaults.
2. Implement BC-01 Function host.
3. Implement BC-02 ingestion code and Function host.
4. Extend Terraform for compute, RBAC, storage container, outputs, and alerts.
5. Add CI/CD workflows and docs.
6. Run validation locally.