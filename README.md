# ContentForge AI

**From an idea to verified content. Powered by collaborating AI agents.**

A multi-agent content workspace built with Next.js, FastAPI, and LangGraph. Follow ten specialized agents in a live control center, inspect claims against stored source passages, revise versioned drafts, and approve a multi-format campaign before export.

> “Supported” means a claim has linked textual evidence. It is not an independent guarantee of factual truth. The no-key demo uses clearly labeled sample references and curated outputs.

## Start in three commands

**Want a free public showcase?** See [FREE_HOSTING.md](FREE_HOSTING.md) for the single-file Static Space page. The user’s hosting screen on 28 October 2026 marks Docker/Gradio Spaces as paid; Static cannot run this application’s backend. The full no-key demo can run on your computer using the [standalone Docker profile](deploy/space/README.md). The Compose deployment below remains the PostgreSQL/Redis option.

Requires Docker Engine and Docker Compose v2.

```bash
python3 scripts/configure.py
docker compose up --build -d
docker compose ps
```

Open port **3000** in your local browser. Choose **Explore the live demo** for the complete electric-vehicle campaign, or create an account for a persistent personal workspace. The generator creates a private, ignored `.env` with a random local database password; existing files are preserved.

For a public domain, follow [the HTTPS deployment steps](DEPLOYMENT.md#https-on-your-own-server). The separate production configuration adds automatic TLS through Caddy, secure cookies, disabled guest sign-in, internal service ports, and persistent certificate storage. You supply the server, domain, and any live model credentials.

Before upgrading a Compose deployment, use the [database backup and restore-check procedure](DEPLOYMENT.md#database-backups-and-restore-checks). The backup command creates a private PostgreSQL archive and checksum without replacing existing backups. `scripts/check_restore.py` can verify that archive by restoring it into a disposable, isolated database and checking its tables and migration.

## Develop without Docker

Requires Python 3.12+, `uv` 0.12.23, and Node.js 22 or newer.

```bash
./scripts/install.sh
./scripts/dev.sh
```

This starts the frontend on port 3000 and backend on port 8000, using SQLite and a local thread pool. Data and LangGraph checkpoints live in `backend/.data/`. Processes must restart after an environment snapshot is restored. PostgreSQL and Redis are used in Docker Compose.

## What is included

- **Agent Control Center:** interactive XYFlow graph, actual backend events, stage inputs/outputs, decision summaries, usage metrics, retry and cancellation controls, persistent event sequence replay.
- **Evidence Intelligence Studio:** source library, highlighted claims, supporting and contradictory passages, many-to-many claim/source links, human evidence assessment, and immutable version history.
- **Ten specialist roles:** supervisor, research, strategy, writer, fact checker, editor, brand guardian, SEO, quality, and export. Research and strategy run in parallel. Quality feedback is bounded. Export is gated by a durable human-approval interrupt.
- **Content Studio:** blog, LinkedIn, Instagram, and YouTube drafts; versioned rich-text editing (bold, italic, and bullet lists), comparisons, anchored comments, revision requests, and Markdown/JSON exports. ZIP packages bundle approved documents, linked evidence, approval records, and file checksums.
- Dashboard, analytics, editorial calendar, brand preferences, dark/light/system themes, command palette, responsive navigation, authentication, and workspace ownership checks.
- Live API connection status, outage recovery, and campaign selection scoped to the signed-in workspace.
- **Workspace usage limits:** persistent daily allowances for starts, retries, and requested revisions, plus a shared active-workflow limit. View usage and the next reset in Settings. Approvals and downloads do not consume the daily allowance.
- **Controlled registration:** production sign-up is closed by default, with terminal account provisioning and server-driven sign-in options. Existing accounts retain access; see [deployment instructions](DEPLOYMENT.md#control-account-registration).
- **Campaign library:** title search, status filters, newest/oldest ordering, and server-side pagination across your campaign history. Filters stay in the page URL for reloads and browser navigation.
- **Duplicate campaigns:** review and edit a saved brief, audience, formats, source selection, and quality settings before launching a separate campaign with fresh drafts and approval.
- PostgreSQL/SQLite persistence, Alembic migrations, Redis/RQ worker, local fallback queue, Docker configuration, tests, and CI.
- **Shared request throttles:** Redis-backed login/write limits across API instances, retry guidance, and write rejection during limiter outages; local development retains an in-memory fallback.
- **Scheduled backup tooling:** private archives and checksum manifests, overlap protection, freshness checks, and generated daily systemd units. See [server installation instructions](DEPLOYMENT.md#daily-backup-schedule-and-freshness-checks); generation does not activate a timer.

## Find a campaign

Open **Overview → Campaign library**. Enter part of a campaign title and press **Search**, then choose a status or creation order. **Active** includes queued and running workflows; **Needs attention** includes failed and interrupted workflows. Use **Previous** and **Next** to browse older results, and click a campaign to open its control center. **Clear filters** restores the full list.

The library refreshes every 15 seconds while visible and also has a manual refresh button. Searches and totals are scoped to your signed-in workspace. Saved page URLs retain filters; opening a URL in another account searches that account's own campaigns.

## Reuse a campaign

1. Open a campaign from **Overview → Campaign library**.
2. In its control center, click **Duplicate campaign**.
3. Review the copied brief, audience, tone, brand voice, formats, sources, execution mode, and advanced settings.
4. Click **Launch agent team** to create a new campaign.

Opening the duplicate form does not start agents. Live campaigns reuse selected source material; demo campaigns create fresh sample references. Drafts, comments, revision feedback, approvals, and schedules stay with the original campaign. If its model provider is unavailable, choose a configured execution mode before launching. The original campaign stays unchanged.

## Move an editorial reminder

Open **Publishing calendar**, find the draft in **Upcoming drafts**, and click **Reschedule**. Choose a future date and time, then click **Save new time**. The calendar moves to the selected date, and the reminder keeps the same approved content version. **Discard changes** leaves the saved reminder unchanged.

Times use your browser’s timezone. If another tab changed the reminder, close the editor and reopen it to use the latest time. Cancelled reminders cannot be rescheduled. Reminders do not publish content to external platforms.

## Download a calendar reminder

In **Publishing calendar → Upcoming drafts**, click **Download .ics** on a reminder. Import the downloaded file using your calendar app’s import command. It contains the saved reminder time, title, and approved version reference. UTC timestamps let calendar apps display the event in their own timezone; demo content is explicitly labeled.

Calendar downloads are snapshots, not subscriptions or invitations. After moving or cancelling a reminder, update or remove an earlier imported event manually; importing a newer file may create a duplicate depending on the calendar app. Downloads contain reminder metadata, not the full content draft, and do not publish content.

## Recover an account

Choose **Sign in → Forgot your password?**, enter your account email, and open the link from your email. Choose and confirm a new password, then sign in again. Links expire after 30 minutes, work once, and are replaced by a newer request. A successful reset signs out existing sessions while preserving your workspace and campaigns.

Email recovery requires the operator's [SMTP configuration](DEPLOYMENT.md#password-recovery-email). If delivery is not configured, the page explains that recovery is unavailable. Request confirmations do not reveal whether an address has an account.

## Verify your account email

Open **Workspace settings → Account email → Send verification link**. Open the email link, sign in to the account that requested it, and click **Verify email**. Settings then shows **Verified**. Links work once, expire after 24 hours, and are replaced by a newer request after a one-minute cooldown.

Verification uses the same SMTP configuration as password recovery. Demo addresses cannot receive email, and unavailable delivery is explained in Settings. Verification is explicitly requested by the account owner; registration does not send mail automatically. Existing accounts remain usable, and this release records email ownership without making verification a requirement for sign-in or content generation.

## Edit and preserve formatting

In **Content Studio**, open a campaign awaiting approval and choose **Edit document**. Bold, italic, bullet lists, nested lists, and line breaks persist when you save a new version. Reloading, reopening the editor, and comparing versions retain that formatting. Markdown and ZIP exports render the supported formatting; JSON includes both the structured document and the exact plain text used for evidence offsets.

Every saved version requires a fresh evidence review, including formatting-only edits. Existing versions remain unchanged. The editor rejects a save if another tab has already created a newer version, preserving your unsaved text so you can copy it before reloading. Older generated documents and API clients that submit plain text remain supported. AI revision rounds produce new generated drafts and do not inherit human formatting automatically.

## Connect live models

For local development, copy `backend/.env.example` to `backend/.env`. For Compose, edit the root `.env`. Set the provider variables on the server, then restart the API and worker:

| Provider | Required configuration |
| --- | --- |
| OpenAI-compatible | `OPENAI_API_KEY`, optional `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| Google Gemini | `GEMINI_API_KEY`, optional `GEMINI_MODEL` |
| Ollama | Running Ollama server, installed model, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |

Keys are never returned to the frontend. Availability badges indicate configuration presence; a live workflow establishes actual connectivity. Live-provider calls may incur charges. Demo mode needs no provider. Test configured model access with `docker compose exec -T api python -m app.provider_check --provider openai` (or `gemini` / `ollama`). This sends one real structured generation request, may incur charges, and reports no credentials or generated text; it does not certify a full campaign.

Live research reads user-provided text/PDFs and securely retrieved, allowlisted URLs. It does **not** perform autonomous web search. Configure trusted source hosts with `SOURCE_HOSTS`. The URL retriever pins public DNS addresses and validates TLS and redirects.

## Verification

```bash
./scripts/test.sh
# With both development servers running:
cd frontend
npx playwright install chromium
npm run test:e2e
```

See [TESTING.md](TESTING.md) for exact coverage and recorded outcomes. See [DEMO.md](DEMO.md) for the presentation walkthrough.

## Documentation

![ContentForge AI agent control center](docs/screenshots/control-center.png)

![Evidence Intelligence Studio](docs/screenshots/evidence-studio.png)

- [Architecture and data flow](ARCHITECTURE.md)
- [Agent contracts and development instructions](AGENTS.md)
- [Evidence semantics and traceability](TRACEABILITY.md)
- [Downloadable campaign packages](EXPORTS.md)
- [Deployment and operations](DEPLOYMENT.md)
- [Tests and validation](TESTING.md)
- [Specification acceptance and launch status](COMPLETION.md)
- [College demonstration](DEMO.md)
- [Viva preparation](VIVA_GUIDE.md)

## Practical limits

This is a working production-oriented reference project, not a claim of audited production readiness. Claim extraction and the quality rubric are deliberately transparent heuristics. Live generation must be reviewed. Export and editorial scheduling work; external social publishing is not connected. The editor preserves supported formatting; arbitrary HTML, links, images, and custom styles are not accepted. The built-in guest demo is intended for local presentations; disable it for public deployments. See deployment notes for scaling, recovery, and security boundaries.

## Check deployment readiness

Before a public deployment, run `docker compose exec -T api python -m app.preflight --provider openai` (or choose `gemini` / `ollama`). It reports configuration issues, database migration status, checkpoint storage, Redis connectivity, and active workers without printing secrets. Use `--offline` to check configuration only, or `--json` for automation. A passing check does not verify live generation or the public website. See [DEPLOYMENT.md](DEPLOYMENT.md#check-deployment-configuration-and-services).
