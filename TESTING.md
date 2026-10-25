# Testing and recorded results

Workspace usage limits, backend tests, Python diagnostics, TypeScript, the production build, and browser journeys were validated on 25 October 2026 in the cloud workspace. The real password-recovery checks were recorded on 24 October, HTTPS deployment and backup/restore on 23 October, and installation, dependency audit, and earlier standalone workflow smoke checks on 22 October. These results describe this checkout; GitHub Actions has its own run history.

| Check | Result |
| --- | --- |
| Frozen installation, `./scripts/install.sh` | Passed: Python and npm dependencies, migrations, checkpoint initialization |
| Backend, `.venv/bin/pytest -q` | 212 passed |
| Python diagnostics, `.venv/bin/ruff check app tests` | Passed |
| Deployment preflight against local Compose | Database, migrations, checkpoints, Redis, and worker checks passed; five expected public-configuration failures for local demo settings |
| Production Compose merge and Caddy configuration | Passed: only proxy publishes ports; secure cookies/HTTPS/no guests enforced; registration closed by default with explicit opt-in tested; separate volumes; Caddy previously validated with network disabled |
| Isolated HTTPS deployment | Passed with a trusted local CA: web/API routing, HTTP redirect, HSTS, secure login, guest rejection, cross-origin rejection, and rejection of an untrusted certificate |
| Account-based HTTPS workflow smoke | Passed: PostgreSQL, Redis/RQ, 10 agents, 187 events, 4 artifacts, 9 ZIP members, and SSE event replay |
| Database backup and isolated restore | Passed: archive checksum verified; all 24 public tables restored with matching row counts and content digests, including application data and checkpoints |
| Alembic schema drift check | Passed on SQLite and PostgreSQL after migration 0004; LangGraph checkpoint tables retain their separate ownership |
| Frontend TypeScript check | Passed |
| Production Next.js build in Docker | Passed |
| npm dependency audit | 0 vulnerabilities reported at validation time |
| Playwright against the production web/API containers | 28 passed in one full run: 3 calendar, 3 duplication, 3 email verification, 3 registration, 3 usage, 3 workflow, 2 campaign-library, 4 connection/account recovery, and 4 password recovery cases |
| Workspace allowances against PostgreSQL | Passed: two separate API processes contending for the last daily attempt admitted exactly one; API usage, cancellation accounting, HTTP 429, and authentication checks passed |
| Controlled registration against PostgreSQL | Passed: actual hidden-input terminal provisioning, closed-sign-up enforcement, concurrent duplicate prevention, and real browser login/settings on mobile |
| Email verification against PostgreSQL | Passed: actual browser confirmation, authentication, session preservation, persisted status, replay rejection, and concurrent confirmation; email captured in process |
| Password recovery against PostgreSQL | Passed: real browser reset, mobile form, session revocation, new-password login, replay rejection, and simultaneous-reset serialization; email delivery captured in process |
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

For an HTTPS deployment with guest sign-in disabled, first provision an account using the [terminal command](DEPLOYMENT.md#control-account-registration), then run:

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

The operator-only preflight change added 38 test cases. No frontend code changed in that release. Its migration test now rejects the previous schema revision until workspace-usage migration 0004 is installed.

The HTTPS deployment change added 35 backend test cases for accepted/rejected domain names, configuration injection, random independent passwords, owner-only file creation, existing configuration preservation, and symlink protection. Python diagnostics also passed for the new deployment scripts and updated smoke script. No frontend code changed in that release.

The HTTPS runtime check used a separate `contentforge-https-validation` Compose project and fresh data volumes, the existing validated application images, and the new Caddy configuration. The test-only override bound the proxy to loopback ports, used `localhost` and a local CA, and adjusted the browser origin to the test port. TLS verification was enabled throughout; an explicit untrusted-root request failed as expected. The real database, migrations, checkpoint tables, queue, worker heartbeat, secure-cookie setting, and disabled guest setting passed preflight. Its public-origin check intentionally rejected localhost. The application flow was verified with password-account login and the labeled demo provider. Public ACME issuance and live model generation were not tested. Disposable test containers and volumes were removed after validation; local demo data was retained.

Backup coverage adds 11 tests for private file/directory permissions, archive checksums, explicit restore-verification limits, local/production project selection, existing files and symlinks, destination races, invalid archive output, failed dumps/catalog checks, timeouts, disk errors, redacted errors, and partial-file cleanup. The archive test reads the inherited file descriptor to catch buffered stream offset errors when piping the backup into a child process.

The real backup was restored with PostgreSQL 16 into a temporary container with networking disabled and its data on tmpfs. `pg_restore --single-transaction --exit-on-error` succeeded; all 24 public tables matched the source database by row count and an ordered digest of complete row contents. The archive SHA-256 checksum also matched. The temporary restore container was removed afterward. This proves recovery of that recorded snapshot; it does not establish scheduled backups, off-server retention, encryption, recovery of Redis queue state, or restoration of every future backup. Application images and frontend code did not change for this operator utility.

Deployment preflight tests cover explicit configuration-only operation, public-origin validation, provider selection, missing connection settings, read-only migration/checkpoint probes, current versus stale worker registrations, correct queue membership, expired registrations, secret-redacted connection errors, CLI JSON and exit codes, and invalid settings that fail before the app can load. The preflight makes no provider generation request and does not prove public deployment readiness.

The container smoke test uses real PostgreSQL persistence, Redis dispatch, an RQ worker, and the PostgreSQL LangGraph checkpointer. It resumes a human-interrupted workflow and checks exported artifacts.

Password recovery adds 21 backend cases covering hashed-token storage, uniform request responses, normalization, persisted request cooldowns, latest-link replacement, expiry, replay, invalid passwords, cross-origin requests, failed-mail redaction and invalidation, single-winner concurrent consumption, revocation of existing sessions, stale-login rejection, preservation of other accounts, missing configuration, recipient/header injection, verified STARTTLS/implicit TLS configuration, and invalid frontend origins. Two migration tests verify that LangGraph's tables are excluded from removal detection while unrelated schema drift still fails.

Four browser cases cover entry from sign-in, unavailable mail configuration, failed availability checks, request retry, matching passwords, reset retry, missing/expired links, URL-fragment removal, refresh behavior, and mobile overflow. These repeatable UI cases intercept mail-related API responses. A separate real browser exercise used an isolated test account in the running PostgreSQL application, captured the delivery callback in process, and completed the actual reset endpoint through the production frontend. It verified that the previous browser session lost access, the old password failed, the new password succeeded, and replay failed. A separate PostgreSQL concurrency check confirmed exactly one reset winner and rejection of session issuance authenticated with the old password.

Email verification adds 12 backend cases for hashed token storage, account/address binding, authentication, unchanged sessions/workspaces, recipient derivation, cooldowns, latest-link replacement, expiry, purpose separation from recovery tokens, failed-mail invalidation and redaction, cross-origin rejection, concurrent single-use consumption, demo/unconfigured delivery behavior, and fragment links through the shared SMTP transport. Migration tests now seed an account at revision 0002 and verify that its credentials survive revisions 0003 and 0004 with no fabricated verification timestamp.

Three browser cases cover settings availability, request retry, explicit confirmation, token removal from the URL, mobile layout, refreshed verified status, signed-out instructions, missing tokens, wrong-account/expired-link feedback, and reload behavior. These repeatable tests intercept verification API responses. A separate real PostgreSQL exercise captured delivery in process, opened the actual confirmation page, rejected anonymous confirmation, verified the account on an explicit button click, retained its session, persisted status after reload, and rejected replay. Another PostgreSQL exercise confirmed that two concurrent confirmations have exactly one winner. A private PostgreSQL backup was taken before the migration.

## Limits of validation

No real SMTP provider credentials were available and no external recovery email was sent. TLS modes are covered with mocked SMTP connections; successful delivery to an external mailbox remains an operator check. Recovery is disabled until mail settings are configured. The migration was checked against the existing PostgreSQL/checkpoint database and local SQLite; a private PostgreSQL backup was taken before the upgrade.

Live paid provider credentials were unavailable, and Ollama was not running; live generation is not verified against external models. General public website retrieval was not exhaustively tested. No public deployment, load test, independent penetration test, or social publishing integration was performed. Semantic claim extraction and quality scores are transparent heuristics, not certified fact checking. GitHub Actions is configured but its remote result must be checked separately.

Controlled-registration coverage adds 14 backend cases: direct registration rejection without session or data changes, separate guest policy, reopening, regular account provisioning with an unverified email and private workspace, login while sign-up is closed, duplicate and concurrent creation, validation, password confirmation, noninteractive-input rejection, unsafe-terminal cancellation, and redacted database failures. Browser coverage checks closed sign-up and disabled guests, existing-account login controls, mobile layout, options-service failure/retry, and a server rejection after a registration form was opened. Closed-policy/error responses are intercepted in those browser cases; backend tests enforce the actual policy. Production configuration validation proves that local open-registration defaults cannot open production accidentally and that explicit `PUBLIC_REGISTRATION=true` works.

An additional check used the real interactive account-creation command in the API container with a pseudo-terminal and confirmed the password was not echoed. Against PostgreSQL, direct registration and guest requests were denied with the corresponding settings disabled, the provisioned account could log in, and two simultaneous duplicate creations yielded one account/workspace. The running API retained its normal local demo policy during this isolated application check. A separate browser signed in through the real login form and opened the new account’s settings at 390px width. No external email or provider generation was invoked.

The first registration browser run passed 24/25 cases. The outage check used a broad alert selector that also matched Next.js’s route announcer; scoping it to the sign-up error resolved the ambiguity. That case passed in a targeted rerun. No application change was needed, and the other passing cases were not rerun.

Workspace usage coverage adds 22 backend cases for authenticated read-only reporting, workspace isolation, accepted-attempt accounting, shared limits across modes, UTC day rollover, configurable zero/invalid limits, cancellation and queue-failure accounting, rejected-request rollback, retries, revision/approval/rejection behavior, rollback of denied reviews, and simultaneous requests for the last daily/active slot. The migration leaves existing accounts unchanged and starts with no usage rows. Configuration validation checks that custom daily/concurrency values reach both API and worker containers.

Three additional browser cases cover persisted counts and account switching, unavailable usage/retry, exhausted and paused states, manual refresh and mobile layout, and preservation of campaign inputs after HTTP 429. These cases run in Asia/Kolkata and verify that midnight UTC is shown as 5:30 AM locally. Error and quota-edge UI responses are intercepted; the normal usage report reads the running API.

Before the usage migration, a private PostgreSQL backup was created and its archive catalog verified. Migration 0004 and Alembic drift checks passed on SQLite and PostgreSQL. An additional PostgreSQL exercise started two separate Python/API processes with separate connections and synchronized admission requests: exactly one consumed the final daily attempt, with one workflow and one persisted counter increment. HTTP checks confirmed authentication, zero remaining allowance, cancellation releasing the active slot without refunding the daily charge, and rejection of another launch. These checks used the labeled demo and replaced queue dispatch for the race; no external model calls were made.
