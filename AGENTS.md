# Working on ContentForge AI

Use the existing checkout. Cloud tasks already have isolated environments; do not create worktrees unless the user explicitly asks.

## Commands

- Install from repository root: `./scripts/install.sh`.
- Run both development services: `./scripts/dev.sh`.
- Backend tests: `cd backend && .venv/bin/pytest -q`.
- Backend diagnostics: `cd backend && .venv/bin/ruff check app tests`.
- Frontend types/build: `cd frontend && npm run typecheck && npm run build`.
- Browser journey: start both services, then `cd frontend && npm run test:e2e`.
- Compose: `python3 scripts/configure.py && docker compose up --build -d`.

Preserve `.env`, `.data`, uploaded references, and user work. Never commit secrets, databases, dependency caches, or test traces. Install with frozen locks. Keep source retrieval, provider requests, and TLS verification enabled.

## Agent roles and tool boundaries

| Agent | Inputs | Output / tools |
| --- | --- | --- |
| Supervisor | Brief and constraints | Bounded execution plan; no external tools |
| Research | Stored source passages | Findings, source IDs, and gaps; stored-source reader |
| Strategy | Brief and audience | Angle, outline, audience, tone |
| Writer | Strategy, evidence, revision feedback | Exactly the requested platform artifacts |
| Fact Checker | Current versions and passages | Conservative claim extraction and passage matching |
| Editor | Current drafts and constraints | Complete edited drafts and notes |
| Brand Guardian | Drafts and brand profile | Complete voice-adjusted drafts |
| SEO & Channels | Drafts and requested channels | Metadata and adapted drafts |
| Quality | Current drafts and evidence statuses | Explainable rubric and bounded revision routing |
| Export | Current versions and recorded human decision | Approved artifact package; no external publishing |

The graph owns routing. Providers cannot invoke arbitrary tools. The only research tool reads stored material. URL ingestion and upload parsing occur through explicit authenticated API operations. Human approval comes only from an authenticated review endpoint.

## Invariants

1. Never invent sources or mark claims supported based only on model confidence.
2. Never carry an evidence status to a changed version without re-evaluation.
3. Export only the exact approved versions. Scheduling is not publishing.
4. Derive UI statuses from backend executions and events. No fake progress timers.
5. Record observable summaries, not hidden model reasoning.
6. Enforce workspace ownership on every resource read/write.
7. Keep demos explicitly labeled, including exports and provider metrics.
8. Preserve and replay event sequences across reconnects.
9. Run meaningful tests after changes to workflow, claims, approvals, or security boundaries.

## Layout

`backend/app/` contains the API, storage, gateway, source tools, and graph. `frontend/components/` contains the connected views. `frontend/lib/` contains typed API contracts and local UI state. `scripts/` contains reproducible install/run checks. API routes are defined in `backend/app/main.py`; Pydantic contracts are in `schemas.py`.
