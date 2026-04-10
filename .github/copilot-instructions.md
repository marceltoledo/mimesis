# Mimesis — Workspace Instructions

> AI pipeline that learns a storyteller's writing style and voice from YouTube videos, then generates and narrates new stories from current news — in the same style and voice as the original author.

---

## Architecture Register

The living record of all Mimesis bounded contexts, components, and domain events is in:

**`.github/docs/mimesis-architecture.md`**

Read this file at the start of any design, implementation, or review task. Every new bounded context and its key decisions are recorded there.

---

## Global Conventions

All agents and engineers MUST follow these conventions. They are finalised and not up for reconsideration per task.

### Infrastructure as Code
- **Terraform** (`azurerm` provider) is the **only** IaC tool for this project.
- Terraform state is stored in an Azure Blob Storage backend with locking.
- No Bicep, ARM templates, or ad-hoc `az` CLI provisioning.

### Identity & Secrets
- All Azure service authentication uses **Azure Managed Identity** with `DefaultAzureCredential`.
- Secrets (API keys, tokens) are stored in **Azure Key Vault** and retrieved at runtime.
- No credentials in environment variables, code, or config files committed to source control.

### Messaging
- **Azure Service Bus** is the standard event bus for all inter-component communication.
- Downstream consumers settle messages (complete/abandon) — no fire-and-forget.

### Storage
- **Azure Blob Storage** for binary/file output (audio, video, transcriptions).
- **Azure Table Storage** for key-value lookups and lightweight registries (e.g. deduplication ledgers).
- **Cosmos DB** only if query patterns require it; justify in an ADR.

### Monitoring
- All components emit logs and errors to **Azure Application Insights**.

### Python Runtime
- Python 3.12+.
- Prefer well-adopted libraries over custom implementations.
- Key libraries already in use: `pytubefix`, `openai-whisper`, `pydub`, `torch`, `google-api-python-client`, `azure-identity`, `azure-keyvault-secrets`, `azure-storage-blob`, `azure-servicebus`.

---

## Solution Design Standards

- Every new feature or component must have a Solution Design document produced by the Solution Architect agent before any code is written.
- Solution Designs follow the DDD methodology defined in `.github/agents/solution-architect.agent.md`.
- After each design is finalised, the architect updates `.github/docs/mimesis-architecture.md`.
