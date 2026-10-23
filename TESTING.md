# Testing and recorded results

Backend tests, Python diagnostics, TypeScript, the production build, and the full browser suite were validated on 23 October 2026 in the cloud workspace. Installation, migration drift, dependency audit, and standalone smoke results below were recorded on 22 October. These results describe this checkout; GitHub Actions has its own run history.

| Check | Result |
| --- | --- |
| Frozen installation, `./scripts/install.sh` | Passed: Python and npm dependencies, migrations, checkpoint initialization |
| Backend, `.venv/bin/pytest -q` | 129 passed |
| Python diagnostics, `.venv/bin/ruff check app tests` | Passed |
| Deployment preflight against local Compose | Database, migrations, checkpoints, Redis, and worker checks passed; four expected public-configuration failures for local demo settings |
| Production Compose merge and Caddy configuration | Passed: only proxy publishes ports; secure cookies/HTTPS/no guests enforced; separate volumes; Caddy validated with network disabled |
| Isolated HTTPS deployment | Passed with a trusted local CA: web/API routing, HTTP redirect, HSTS, secure login, guest rejection, cross-origin rejection, and rejection of an untrusted certificate |
| Account-based HTTPS workflow smoke | Passed: PostgreSQL, Redis/RQ, 10 agents, 187 events, 4 artifacts, 9 ZIP members, and SSE event replay |
| Alembic schema drift check | No new upgrade operations detected |
| Frontend TypeScript check | Passed |
| Production Next.js build in Docker | Passed |
| npm dependency audit | 0 vulnerabilities reported at validation time |
| Playwright against the production web/API containers | 15 passed in one full run: 3 calendar, 3 duplication, 3 workflow, 2 campaign-library, and 4 recovery checks |
| PostgreSQL + Redis/RQ end-to-end smoke | Passed: 10 agents, 187 persisted events, 4 artifacts, 9 ZIP members with verified checksums |
| SQLite + local thread pool development smoke | Passed: 10 agents, 187 persisted events, 4 artifacts, 9 ZIP members with verified checksums |

## Repeat the checks

```bash
./scripts/install.sh
./scripts/test.sh
```

In another terminal, start the development services with `./scripts/dev.sh`. Then:

```bash
python3 scripts/smoke.py
cd frontend
npx playwright install chromium
npm run test:e2e
```

Playwright uses `/usr/bin/chromium` when available, or its installed browser otherwise. Set `CHROMIUM_PATH` for a custom executable. Set `PLAYWRIGHT_BASE_URL` when testing a different web port. The responsive journey has a longer timeout because it visits nine views at three viewport sizes.

For the production stack:

```bash
python3 scripts/configure.py
docker compose up --build -d
python3 scripts/smoke.py --base-url http://localhost:3000
```

For production configuration checks, run `python3 scripts/check_deployment.py` with Docker Compose 2.24.4 or newer. It resolves both configurations with synthetic values, deliberately supplies insecure local defaults, and checks that the production override still enforces the intended boundaries. It never starts containers or reads the operator's `.env` files. GitHub Actions includes a separate deployment job for this check and Caddy configuration validation; its remote result must be checked separately.

For an HTTPS deployment with guest sign-in disabled, first create an account, then run:

```bash
python3 scripts/smoke.py --base-url https://your-domain.example.com --email your-account@example.com
```

The script prompts for the existing account password, or reads `CONTENTFORGE_SMOKE_PASSWORD` when supplied by automation. It creates a verification campaign in that account. `--ca-file /path/to/trusted-ca.pem` supports an internal test CA while retaining certificate and hostname verification. The smoke test also reads a persisted SSE event using `Last-Event-ID` through the deployment proxy.

`scripts/capture.mjs` captures real screenshots from a running demonstration. The checked-in screenshots were captured against the production containers.

## Coverage

Backend tests exercise the complete demo graph, parallel branch join, evidence/version integrity, source relationships, event sequencing, editing and stale versions, human approval/revision/rejection, cancellation, scheduling, comments, analytics, checkpoint recovery, bounded retries, ownership, cross-origin writes, upload/body limits, provider contracts, and error redaction. Provider adapters use mocked HTTP responses, including transient failure retries. Conservative evidence matching includes a negated-sentence regression.

Browser tests exercise the graph inspector, disputed evidence, editing and comments, approval, download, calendar, analytics, preferences, project/campaign creation, mobile navigation, responsive views at 390/768/1440 pixels, and SSE replay from a saved sequence cursor.

Recovery tests exercise failed health checks and successful retries, browser offline/reconnect events, temporary identity lookup failures, guest-session protection during an outage, failed sign-out, and switching to a new account without carrying over a campaign selection. Failure responses are intercepted in the browser; normal requests use the running API.

Export tests inspect ZIP contents, manifest checksums, reproducible downloads, Unicode text, safe archive paths, ownership, approved-version enforcement across all formats, and evidence relationships restricted to approved versions. The browser journey also downloads ZIP files and verifies that the saved export preference is used.

Campaign library tests seed 125 persisted workflows and verify pagination beyond the legacy picker limit, stable ordering when timestamps tie, literal wildcard searches, combined status/title filters, input bounds, and workspace isolation for both results and counts. Browser coverage checks paging, search, status and sort filters, reload/back navigation, empty/out-of-range pages, mobile layout, and retry after an API error.

The final campaign-library browser run also verifies that a selected campaign remains available when absent from the recent-items picker. The mobile width check waits for the responsive sidebar transition to settle before measuring overflow.

Campaign duplication tests verify that reading a reusable brief performs no writes, enforces workspace ownership, excludes project IDs and internal revision feedback, preserves live source selection and custom constraints, and resets demo references. Launching a copy of an approved campaign produces new drafts that require their own approval, while the original remains unchanged. Browser tests cover prefilled fields and custom tones, edited advanced settings retained when collapsed, separate campaign creation, missing-campaign retry, unavailable-provider handling, older selected sources, preserving edits during a settings refresh failure, and the mobile layout. The unavailable-provider browser scenario uses intercepted brief/settings/source fixtures and makes no live model calls.

Calendar rescheduling tests verify timezone normalization, future-date validation, workspace ownership, cross-origin write rejection and trusted-origin CORS preflight, unchanged approved-version references, atomic rejection of stale updates, cancelled reminders, and rejection of attempts to change the pinned content. Browser tests run in Asia/Kolkata and check local time prefilling, moving a reminder into another month, persistence after reload, discarding edits, validation errors, mobile layout, cancellation, server failures, and stale-editor recovery.

Calendar download tests inspect MIME type, attachment filename, private/no-store handling, CRLF line endings, UTC timestamps, stable event identifiers after rescheduling, the pinned version reference, demo labels, workspace isolation, and cancelled-reminder rejection. Unicode titles are folded to at most 75 UTF-8 octets per line without splitting characters; escaped title data cannot inject additional events or attendees. Browser coverage downloads real files, checks updated timestamps after a move, verifies retry after an intercepted server error, and inspects the mobile controls. Imports into third-party calendar applications have not been tested; imported files are manual snapshots with no synchronization.

The operator-only preflight change adds 38 test cases. Frontend/browser results above remain from the preceding calendar-download validation; no frontend code changed for preflight.

The HTTPS deployment change adds 35 backend test cases for accepted/rejected domain names, configuration injection, random independent passwords, owner-only file creation, existing configuration preservation, and symlink protection. Python diagnostics also passed for the new deployment scripts and updated smoke script. No frontend code changed; the prior browser/build results remain applicable to that code.

The HTTPS runtime check used a separate `contentforge-https-validation` Compose project and fresh data volumes, the existing validated application images, and the new Caddy configuration. The test-only override bound the proxy to loopback ports, used `localhost` and a local CA, and adjusted the browser origin to the test port. TLS verification was enabled throughout; an explicit untrusted-root request failed as expected. The real database, migrations, checkpoint tables, queue, worker heartbeat, secure-cookie setting, and disabled guest setting passed preflight. Its public-origin check intentionally rejected localhost. The application flow was verified with password-account login and the labeled demo provider. Public ACME issuance and live model generation were not tested. Disposable test containers and volumes were removed after validation; local demo data was retained.

Deployment preflight tests cover explicit configuration-only operation, public-origin validation, provider selection, missing connection settings, read-only migration/checkpoint probes, current versus stale worker registrations, correct queue membership, expired registrations, secret-redacted connection errors, CLI JSON and exit codes, and invalid settings that fail before the app can load. The preflight makes no provider generation request and does not prove public deployment readiness.

The container smoke test uses real PostgreSQL persistence, Redis dispatch, an RQ worker, and the PostgreSQL LangGraph checkpointer. It resumes a human-interrupted workflow and checks exported artifacts.

## Limits of validation

Live paid provider credentials were unavailable, and Ollama was not running; live generation is not verified against external models. General public website retrieval was not exhaustively tested. No public deployment, load test, independent penetration test, or social publishing integration was performed. Semantic claim extraction and quality scores are transparent heuristics, not certified fact checking. GitHub Actions is configured but its remote result must be checked separately.
