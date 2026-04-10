# Agent Knowledge Base

This document captures durable operational learnings for repository agents.

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
