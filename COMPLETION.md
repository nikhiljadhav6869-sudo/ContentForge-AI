# ContentForge AI — V1 acceptance and launch status

This checklist maps the repository to the 18 acceptance criteria in [the original specification](docs/SPECIFICATION.md#20-final-project-acceptance-criteria). The reproducible demo and application features are implemented. Public production launch remains dependent on an actual hosting destination, live provider configuration, and operational verification; it is not represented as completed by local tests.

## Specification acceptance

| # | Acceptance criterion | Implementation and verification |
| --- | --- | --- |
| 1 | Connected premium frontend | Landing, dashboard, creation, control center, evidence, content, approvals, analytics, calendar, and settings; browser journeys cover navigation and phone/tablet/desktop layouts. |
| 2 | Working FastAPI backend | Authenticated APIs, validated inputs, workspace ownership, read/write flows, health checks, and automated backend tests. |
| 3 | Database persistence | PostgreSQL deployment and SQLite development; Alembic migrations through `0005`; versions, evidence, events, approvals, reminders, and usage persist. |
| 4 | Real LangGraph orchestration | Typed graph state, parallel research/strategy, conditional revisions, checkpointed human review, bounded termination, and Redis/RQ dispatch. |
| 5 | Interactive agent visualization | XYFlow graph supports selection, zoom/pan, inspector details, and visible workflow states. |
| 6 | Runtime-driven activity | Backend events and persisted sequence IDs drive the UI; SSE replay recovers missed events. |
| 7 | Inspectable inputs/outputs | Stored agent inputs, structured outputs, observable summaries, errors, retry and usage records; no hidden reasoning transcripts. |
| 8 | Claim extraction | Deterministic claim extraction from each version's canonical text; offsets remain correct with emoji/Unicode. |
| 9 | Evidence links | Stored passages and many-to-many claim relations; supporting, contradictory, partial, mention, and insufficient-evidence assessments. |
| 10 | Interactive claim highlighting | Claim selection links the document, evidence inspector, source passages, agent execution, and version history. |
| 11 | Content revision loop | Bounded automatic revisions, human revision requests, immutable versions, rich-text editing, and stale-edit rejection. |
| 12 | Explainable quality evaluation | Stored weighted rubric and category scores; factual warnings survive a high numerical score. |
| 13 | Human approval | Authenticated approval/rejection/revision, warning acknowledgement, exact version IDs, and approval-gated export. |
| 14 | Multiple content platforms | Blog, LinkedIn, Instagram, and YouTube artifacts. Full four-format demo is tested; live-provider adapters have automated contract tests, while actual external generation still needs configured services. |
| 15 | Exportable artifacts | Markdown, JSON, and deterministic ZIP packages with approval/evidence references and checksums; supported rich-text formatting is retained. |
| 16 | Working no-key demonstration | Complete EV campaign executes through the graph, disputed claim, revision, review, approval, and download; demo provenance is labeled. |
| 17 | Automated tests | Backend/security/workflow tests, browser journeys, operator-tool tests, production build and CI definitions; see [recorded results](TESTING.md). |
| 18 | Deployment configuration | Frozen installation, Compose/PostgreSQL/Redis, standalone frontend, HTTPS proxy configuration, preflight, backups, and generated systemd schedules with server installation instructions. |

## Reproduce the project

Follow [README.md](README.md) for the three-command Docker startup or `./scripts/install.sh` and `./scripts/dev.sh` for development. Open the app, choose **Explore the live demo**, inspect its agent graph and evidence, edit a draft, review and approve, then download a campaign package. This journey needs no paid AI or email credentials.

For independent verification:

```bash
./scripts/test.sh
# With the app running on its configured web port:
cd frontend
npm run test:e2e
```

Use `PLAYWRIGHT_BASE_URL` when the web service uses a port other than 3000. Recorded validation ran against the workspace's production-built Compose services on port 3100; this is a local test deployment, not a public site.

## External launch dependencies

The following cannot be established by generating more repository files:

1. **Hosting and domain:** choose the deployment machine/service and domain, configure DNS, then run the [HTTPS deployment procedure](DEPLOYMENT.md#https-on-your-own-server). Validate public TLS, login, SSE, and an end-to-end campaign from outside that server. No external hosting or domain has been provisioned here.
2. **Live AI:** configure OpenAI-compatible/Gemini credentials or a reachable Ollama installation in private server environment settings. Run `python -m app.provider_check --provider ...` inside the backend, then review a full live campaign with supplied sources. The completion check found no configured OpenAI/Gemini keys and no reachable Ollama models; no live-model success is claimed.
3. **Email:** configure SMTP and verify real delivery of recovery and verification links for a controlled account. Delivery is currently unconfigured; tests capture email in process rather than sending it externally.
4. **Operations:** install/enable the generated backup timer on the actual server, confirm it runs after reboot, test restore, arrange encrypted off-server copies/retention, and connect failure monitoring. The workspace has no running systemd manager; generated timers are not active.
5. **Public access:** keep registration/guests closed until operator access, provider spending limits, global abuse controls, and monitoring are ready. Existing per-workspace admission limits count attempts, not currency costs.

Do not paste provider keys, SMTP passwords, or server credentials into issues, commits, or public documentation. They belong in the deployment's private environment/secret configuration.

## Explicit product boundaries

Evidence matching and quality scores are inspectable heuristics, not independent fact certification. Live research uses supplied documents and allowlisted URL retrieval; autonomous web search is not implemented. Calendar entries are editorial reminders, not social publication. Export is complete without a social-platform integration. SSO, MFA, shared-workspace roles, subscriptions/billing, and external publishing are future enhancements rather than hidden prerequisites for the specified V1 demonstration.

Rich-text editing supports paragraphs, bold/italic, bullets, nested bullets, and line breaks. Arbitrary HTML, images, links, and custom styling are rejected. Evidence inspection operates on canonical text; each new version needs its own evidence review. A generated revision is a new draft and does not automatically retain manual formatting.
