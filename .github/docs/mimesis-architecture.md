# Mimesis — Architecture Register

> Living record of all bounded contexts, components, domain events, and global ADRs.
> **Updated by the Solution Architect agent after every finalised design.**

For operational agent conventions and learned workflows, see `.github/docs/agent-knowledge-base.md`.

---

## System Overview

```
YouTube (search & download) → Transcription → Style Learning → Story Generation → Voice Synthesis → Publish
```

---

## Bounded Context Map

| # | Bounded Context | Responsibility | Status |
|---|---|---|---|
| 1 | **Video Discovery** | Search YouTube by keyword, deduplicate, emit `VideoDiscovered` events | Designed |
| 2 | **Video Ingestion** | Consume discovered video events, persist video/audio/metadata artifacts, emit `VideoIngested` events | Designed |
| 3 | **Transcription** | Transcribe audio to text using Whisper, store transcription | Prototype (notebook) |
| 4 | **Style Learning** | Analyse transcriptions, learn narrator's writing style, store style profile | Not started |
| 5 | **Story Generation** | Generate new stories from news using learned style | Not started |
| 6 | **Voice Synthesis** | Clone narrator voice, narrate generated story, produce audio | Not started |
| 7 | **Publishing** | Store and serve final audio story | Not started |

---

## Component Registry

### BC-01 · Video Discovery

**Solution Design**: Created April 2026

**Aggregate Root**: `SearchJob`

**Key Domain Objects**:

| Object | Type | Description |
|---|---|---|
| `SearchJob` | Aggregate Root | Orchestrates a keyword search run |
| `VideoSearchResult` | Entity | A video returned by YouTube for a given search |
| `SearchQuery` | Value Object | Keyword + optional filters |
| `SearchFilters` | Value Object | `language`, `published_after`, `video_duration`, `region_code` |
| `VideoMetadata` | Value Object | Full YouTube API v3 metadata fields |
| `VideoDiscovered` | Domain Event | Emitted once per unique `videoId` globally |

**Domain Events**:

| Event | Producer | Consumer | Queue |
|---|---|---|---|
| `VideoDiscovered` | Video Discovery | Video Ingestion | `sb-queue-video-discovered` |

**Key Decisions**:
- `google-api-python-client` for YouTube Data API v3 (search + full metadata in batch)
- Auto-pagination up to configurable `max_results` ceiling
- Global deduplication via **Azure Table Storage** Discovery Ledger (`PartitionKey='video'`, `RowKey=videoId`)
- API key stored in **Azure Key Vault**; retrieved via Managed Identity
- Events published to **Azure Service Bus** with `messageId = videoId` (duplicate detection enabled)

**Terraform Resources**:
- `azurerm_servicebus_namespace` + `azurerm_servicebus_queue` (name: `sb-queue-video-discovered`)
- `azurerm_storage_table` (Discovery Ledger, in existing Storage Account)
- `azurerm_key_vault_secret` (`youtube-api-key`)
- `azurerm_role_assignment` (Key Vault Secrets User, Storage Table Data Contributor, Service Bus Data Sender)

---

### BC-02 · Video Ingestion

**Solution Design**: Created April 2026

**Aggregate Root**: `VideoIngestionAggregate`

**Key Domain Objects**:

| Object | Type | Description |
|---|---|---|
| `VideoIngestionAggregate` | Aggregate Root | Coordinates ingestion lifecycle for one `videoId` |
| `IngestionRecord` | Entity | Tracks status, retries, and completion timestamps |
| `IngestionArtifactSet` | Entity | Blob artifact references for source video, audio, and metadata |
| `BlobArtifactPath` | Value Object | Canonical artifact storage path |
| `IngestionStatus` | Value Object | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED` |
| `VideoIngested` | Domain Event | Emitted after all required artifacts are durably persisted |

**Domain Events**:

| Event | Producer | Consumer | Queue |
|---|---|---|---|
| `VideoDiscovered` | Video Discovery | Video Ingestion | `sb-queue-video-discovered` |
| `VideoIngested` | Video Ingestion | Transcription | `sb-queue-video-ingested` |

**Key Decisions**:
- Trigger model: consume `VideoDiscovered` from Service Bus (`sb-queue-video-discovered`)
- Download source media with `pytubefix` (complements BC-01 `google-api-python-client` usage)
- Extract audio to MP3 via `ffmpeg`/`pydub`
- Persist artifacts in Blob Storage (`raw-videos`, `extracted-audio`, `video-metadata`)
- Metadata blob stores ingestion-owned metadata only (no full event envelope)
- Deduplication/idempotency via Azure Table Storage ingestion ledger (`PartitionKey='video'`, `RowKey=videoId`)
- Emit `VideoIngested` only after artifact completeness (video, audio, metadata)
- Apply raw-video retention of 30 days via Blob lifecycle rules

**Terraform Resources**:
- `azurerm_servicebus_queue` (name: `sb-queue-video-ingested`)
- `azurerm_storage_management_policy` (30-day retention for raw video blobs)
- `azurerm_storage_table` (Ingestion Ledger)
- `azurerm_role_assignment` (Service Bus Data Receiver/Sender, Blob Data Contributor, Table Data Contributor)

---

## Global Architecture Decision Records

These ADRs apply to **all** bounded contexts and must not be re-litigated per component.

### G-ADR-01: Terraform as the only IaC tool

- **Decision**: `azurerm` provider Terraform for all Azure resource provisioning.
- **Rejected**: Bicep (valid but team preference is Terraform), ad-hoc `az` CLI.
- **Consequences**: Terraform CLI required in CI/CD; remote state in Azure Blob Storage with locking.

### G-ADR-02: Azure Managed Identity + DefaultAzureCredential for all auth

- **Decision**: No secrets in environment variables or config files. All Azure SDK clients use `DefaultAzureCredential`.
- **Rejected**: Service principal client secrets in `.env` files — rotation risk, leak risk.
- **Consequences**: Requires Managed Identity assignment on all compute resources.

### G-ADR-03: Azure Service Bus for all inter-component messaging

- **Decision**: Service Bus Standard tier; consumers settle messages (complete/abandon).
- **Rejected**: Storage Queue (lacks duplicate detection, session support); Event Grid (push-only, not pull-queue).
- **Consequences**: Service Bus namespace shared across bounded contexts; each BC gets its own queue.

### G-ADR-04: Azure Table Storage for lightweight key-value registries

- **Decision**: Use Table Storage for deduplication ledgers and lookup tables. Same Storage Account as Blob.
- **Rejected**: Cosmos DB (overkill for key lookups at MVP scale), Redis (ephemeral, adds infra complexity).
- **Consequences**: No complex query support — Table Storage is point-read/write only by design.

### G-ADR-05: Azure Application Insights for all monitoring

- **Decision**: Every component logs structured events and exceptions to Application Insights.
- **Consequences**: Single App Insights instance shared across all bounded contexts; use `cloud_RoleName` to distinguish components.

---

## CI/CD Pipeline Architecture

### Workflow Layout

All GitHub Actions workflows live in `.github/workflows/`. Files with an `_` prefix are reusable (`workflow_call`) only; files without a prefix are top-level entrypoints.

```
_tf-apply.yml           — Reusable: Terraform init → plan → apply
_deploy-bc.yml          — Reusable: Package + blob-upload a single BC (owns its own pip install)
_smoke-bc01.yml         — Reusable: BC-01 HTTP endpoint smoke test
_smoke-bc02.yml         — Reusable: BC-02 two-job smoke (smoke-sb-send → smoke-blob-poll)
dev-rollout.yml         — Orchestrator: DEV full chain
dev-smoke.yml           — Thin dispatcher: BC-01 + BC-02 smoke in parallel for env=dev
lint-test.yml           — Python lint + unit tests
terraform-validate.yml  — Terraform fmt + validate
create-issue-branch.yml — Auto-creates feature branches from issues
```

### Job Dependency Graph (dev-rollout.yml)

```
terraform-dev
    ├── deploy-bc01-dev  ──► smoke-bc01-dev
    └── deploy-bc02-dev  ──► smoke-bc02-dev
                                 ├── smoke-sb-send
                                 └── smoke-blob-poll (needs: smoke-sb-send)
```

BC-01 and BC-02 deploy **in parallel** after Terraform completes. Smoke jobs are independent of each other, so a BC-02 blob-poll timeout does not block BC-01 result visibility.

### CI Architecture Decision Records

| ADR | Decision | Rationale |
|---|---|---|
| ADR-CI-01 | `workflow_call` reusable workflows over copy-paste or job matrix | Enables independent re-run of any stage; eliminates duplication for PROD |
| ADR-CI-02 | `_` prefix for reusable files | Visually distinguishes entrypoints from reusable building blocks |
| ADR-CI-03 | BC-02 smoke split into `smoke-sb-send` + `smoke-blob-poll` jobs | Independent visibility of SB send vs 90-second blob poll |
| ADR-CI-04 | PROD Terraform runs in its own job | Supports environment protection rules and `required_reviewers` gate before apply |
| ADR-CI-05 | `_deploy-bc.yml` owns its own `pip install` | No hidden dependency coupling between BC build artefacts |

---

## Domain Event Catalogue

| Event | Producer BC | Consumer BC | Service Bus Queue | Schema Version |
|---|---|---|---|---|
| `VideoDiscovered` | Video Discovery | Video Ingestion | `sb-queue-video-discovered` | v1 |
| `VideoIngested` | Video Ingestion | Transcription | `sb-queue-video-ingested` | v1 |

---

## Ubiquitous Language (Global)

Terms that are shared across all bounded contexts and must be used consistently.

| Term | Definition |
|---|---|
| **Video** | A YouTube video identified by its YouTube `videoId` |
| **Narrator** | The human storyteller whose style and voice Mimesis learns and reproduces |
| **Story** | A narrated audio piece generated by Mimesis in the narrator's style and voice |
| **Pipeline** | The end-to-end sequence: Discover → Ingest → Transcribe → Learn → Generate → Synthesise → Publish |
| **Bounded Context** | A self-contained domain area with its own model, team ownership, and deployment boundary |
| **Domain Event** | An immutable record of something that happened, used to communicate between bounded contexts |
| **Artifact Completeness** | State where source video, extracted audio, and metadata artifacts are all present and readable in Blob Storage |
