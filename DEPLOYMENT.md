# Deployment

## Local Docker Compose

```bash
python3 scripts/configure.py
docker compose up --build -d
docker compose ps
docker compose logs --tail=50 api worker web
```

The root `.env` is ignored and initially gets a generated database password. Keep it private. Compose provides PostgreSQL 16, Redis 7, the FastAPI container, a separate RQ worker, and the Next.js standalone frontend. PostgreSQL/Redis/API/web host bindings are loopback-only by default. Access the web service on port 3000 from the deployment machine. Database, queue, and backend volumes persist across container restarts. `docker compose down` retains them; `down -v` destroys them.

The API runs Alembic and checkpoint setup before listening. The worker starts after API health succeeds. Run migrations as a separate release task before scaling API replicas. All backend processes must use the same `DATABASE_URL`, `CHECKPOINT_URL`, and `REDIS_URL`.

Change `WEB_PORT` or `API_PORT` in the root `.env` if local ports are occupied. `FRONTEND_ORIGIN` must match the browser origin, including port. The root file is for Compose; local non-container Python reads `backend/.env`.

## HTTPS on your own server

The production override runs Caddy, the frontend, API, PostgreSQL, Redis, and the worker together. Use a Linux server with Docker Engine, **Docker Compose 2.24.4 or newer**, and a public domain you control. Point its A record (and AAAA record only if IPv6 works) at the server, and allow inbound TCP ports 80/443. UDP 443 is optional for HTTP/3. Caddy obtains and renews public certificates once DNS and reachability are correct.

From the repository root on that server, replace the example domain with yours:

```bash
python3 scripts/configure_production.py --domain studio.example.com
```

This creates `.env.production` with owner-only permissions and a random database password. Existing files are preserved, including the local `.env`. Open `.env.production` in your editor and add the credentials/model for your chosen provider. Keep it private and retain a protected backup. The generator validates hostname syntax; it does not register a domain, check DNS ownership, or buy hosting.

Validate the deployment structure and start the stack:

```bash
python3 scripts/check_deployment.py
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml up --build -d
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml logs --tail=50 proxy
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml exec -T api python -m app.preflight --provider openai
```

Select `gemini` or `ollama` for preflight if appropriate. `check_deployment.py` uses synthetic configuration to check the Compose merge; it does not inspect your credentials or contact your server. The container preflight checks the running backend. Provision an account with the terminal command below, then open `https://` followed by your domain and sign in. Verify its demo workflow through HTTPS with:

```bash
python3 scripts/smoke.py --base-url https://studio.example.com --email your-account@example.com
```

The script prompts privately for the existing account's password, then creates a labeled verification project/campaign and checks workflow execution, event replay, human approval, and exports. For automation, provide `CONTENTFORGE_SMOKE_PASSWORD` through your secret manager; do not put passwords in command arguments. Signed-in accounts can run the labeled demo without a model key; a successful live campaign is still required to verify your chosen provider. Guest demo sign-in is disabled.

Only Caddy publishes host ports. Requests under `/api` go directly to FastAPI, with immediate event-stream flushing; other requests go to Next.js. Production enforces the HTTPS browser origin, secure session cookies, and disabled guest access even if local demo defaults are present. HSTS applies to this hostname only. API, database, queue, and frontend ports remain internal. Certificate/account state persists in named Caddy volumes.

The Compose project is named `contentforge-production`, with its own database and other volumes. It does not import accounts or campaigns from the local `contentforge` project. Use the same `--env-file` and both `-f` arguments for every production operation, including restart, logs, exec, and down. Keep the project name stable so Compose can find the existing volumes. Do not regenerate a database password against an existing PostgreSQL volume: changing the file alone does not rotate the database password. Never use `down -v` on a deployment whose data you need.

For upgrades, back up PostgreSQL and configuration first, fetch the reviewed release, and repeat the production `up --build -d` command. This single-server setup can have brief downtime during an upgrade. For a build requiring the trusted CA override below, add `-f compose.ca.yaml` after `-f compose.production.yaml` and supply `CONTENTFORGE_BUILD_CA` when building.

Public account registration is closed by default in production Compose. Existing accounts continue to work. Each account has its own workspace, but configured provider credentials are server-wide. Closing registration controls new account access; it does not impose spending limits on existing accounts. The operational limits below still apply; this configuration alone does not establish production readiness. Public DNS and certificate issuance must be checked on your actual server.

## Control account registration

Production Compose defaults to `PUBLIC_REGISTRATION=false`, including when upgrading an existing configuration that omits this setting. This overrides the local `REGISTRATION_ENABLED=true` default. Guest creation remains disabled independently. The landing page reads the server policy, offers existing-account sign-in, and explains when registration is closed. The API rejects direct registration requests too.

Create a regular account from a trusted, interactive server terminal:

```bash
docker compose --env-file .env.production -f compose.yaml -f compose.production.yaml exec api python -m app.create_account --email your-account@example.com --name "Your Name"
```

Do **not** add `-T`: the command requires a terminal and prompts twice for a hidden 10–128 character password. It refuses piped input, command-line passwords, and terminals that cannot hide password entry. The database must already be migrated. Account and private workspace creation is atomic; a duplicate email fails without replacing credentials, sessions, or workspace data. The account is a regular user, with no admin role or automatic email verification. It receives no email and no automatic session. Use your own account credentials or an appropriate secure handoff when provisioning for another person.

For local Compose, use `docker compose exec api python -m app.create_account --email your-account@example.com`. Outside Docker, run `.venv/bin/python -m app.create_account --email your-account@example.com` from `backend/` with the intended database configuration. Never change database connection settings merely to create an account.

To deliberately open production sign-up, set `PUBLIC_REGISTRATION=true` in `.env.production`, then repeat the production `up -d` command to recreate API and worker with the new configuration. `REGISTRATION_ENABLED` controls standalone/local deployments; set it to `false` there to close sign-up. Restart/recreate all API replicas after changes. Preflight flags open registration until aggregate spending and public-access abuse controls are in place; opt-in does not bypass that diagnostic. Closing sign-up preserves current sessions and does not disable login, password recovery, or email verification. Guest creation is a separate `DEMO_AUTH` setting; production Compose always disables it.

## Check deployment configuration and services

Run the operator preflight from the API container so it reads the same configuration as the backend:

```bash
docker compose exec -T api python -m app.preflight --provider openai
```

Choose `openai`, `gemini`, or `ollama` explicitly. Add `--json` for machine-readable output. For a configuration-only check outside Docker:

```bash
cd backend
.venv/bin/python -m app.preflight --provider openai --offline --json
```

Exit **0** means the checks in the reported scope passed; exit **1** means at least one failed (invalid command arguments use exit **2**). With `--offline`, no services are contacted and a successful result applies only to configuration. Fix the reported environment settings in your deployment configuration, then rerun the command. It does not rewrite configuration, migrate databases, change queue registrations, enqueue workflows, or call an AI provider.

Configuration checks cover the exact public HTTPS frontend origin, secure cookies, guest sign-in disabled, public registration closed, PostgreSQL application/checkpoint URLs, Redis, and fields for the selected provider. Service checks use read-only database queries to compare the installed Alembic revision with this release and locate checkpoint tables. Redis is pinged, then its worker registrations are inspected without cleaning or modifying them. A worker must listen on `contentforge`, be idle or busy, have an unexpired registration, and have a heartbeat within 450 seconds. Failed or unconfigured services are reported separately; a passing Redis ping alone does not imply a worker is available.

Connection values, provider keys, worker names, and raw exception details are omitted from both output formats. Provider fields being present does **not** prove credentials are valid or a model can generate content. Public DNS/HTTPS, reverse-proxy behavior, backups, capacity, and an actual end-to-end workflow still need verification. The command reports these limits even when its checks pass. Local demo defaults intentionally fail the public-deployment configuration checks; keep them for local development rather than changing them just to obtain a passing report.

## Hosted frontend

The `frontend/` directory is compatible with a Next.js host such as Vercel. Set the root directory to `frontend`, install with `npm ci`, build with `npm run build`, and configure server-only `BACKEND_URL` **before the build**. It is used in the API rewrite. Do not put provider keys in `NEXT_PUBLIC_*` variables.

Deploy the backend separately on a persistent container service with PostgreSQL, Redis, and an RQ worker. Set `FRONTEND_ORIGIN` to the exact HTTPS frontend origin, `SECURE_COOKIES=true`, and `DEMO_AUTH=false`. If the hosting provider limits SSE duration, EventSource reconnects using the last event sequence. Proxies must preserve cookies, disable event-stream buffering/compression, and support streaming. A short HTTP timeout must not interrupt workflow workers.

No hosting account, DNS record, TLS certificate, or external publication integration is provisioned by this repository.

## Password recovery email

Configure these server-only variables in `.env.production` for production Compose, root `.env` for local Compose, or `backend/.env` for non-container development:

| Variable | Purpose |
| --- | --- |
| `SMTP_HOST` | Mail provider's SMTP hostname; empty disables recovery |
| `SMTP_PORT` | Provider's port, normally 587 for STARTTLS or 465 for implicit TLS |
| `SMTP_SECURITY` | `starttls` (default) or `ssl`; plaintext transport is not supported |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Provider's SMTP credentials; both set or both empty for an authenticated relay environment |
| `SMTP_FROM` | A single sender address authorized by your mail provider |

`FRONTEND_ORIGIN` must be the exact public HTTPS origin for account email links. HTTP is allowed only for loopback development. Links use this configured origin, never the request's Host header. Restart/recreate the API after configuration changes; Compose environment updates require `up -d` with the appropriate env file and overrides. Existing deployments need migrations through `0004`, applied automatically when the rebuilt API starts; local development uses `cd backend && .venv/bin/alembic upgrade head`.

Configure the sender/domain with your mail provider and verify delivery to an account you control before inviting users. SMTP uses certificate/hostname verification, a ten-second socket timeout, and no fallback to plaintext. No provider-specific SMTP credentials are included. The public availability endpoint reports configuration presence, not verified mailbox delivery; deployment preflight does not test SMTP.

Forgot-password requests receive the same accepted response for known and unknown valid addresses. Actual delivery runs after the HTTP response and is best effort, with a persisted 60-second cooldown per account in addition to the existing per-process IP throttle. There is no durable mail queue or automatic retry. Delivery errors produce a fixed server warning without addresses, tokens, credentials, or SMTP exception details; a failed link is invalidated. Check mail-provider operations if users do not receive messages.

Reset links expire after 30 minutes and are single-use. Only a token hash is stored in PostgreSQL/SQLite. Tokens travel in the email link fragment, which is excluded from HTTP request URLs, and are removed from the browser address bar once read. The reset form retains the token only in memory; reloading requires reopening the complete email link. Do not configure infrastructure to log reset request bodies. Successful resets revoke every existing session for that account and require a fresh sign-in. Other accounts, workspaces, campaigns, and content remain unchanged. SSO and MFA remain separate features.

### Account email verification

Signed-in owners request verification from **Settings → Account email**. No additional mail credentials are needed. Messages are sent only after an explicit request, to the stored account address; a request body cannot change the recipient. Reserved `@contentforge.local` demo addresses cannot receive verification mail. Requests have a persisted one-minute cooldown, use best-effort background delivery, and log only fixed error messages on failure. A failed delivery invalidates its link without discarding the cooldown.

Verification links expire after 24 hours and require both the token and a session for the matching account. The page shows the signed-in address and requires an explicit **Verify email** click; merely opening a link never marks an account verified. Tokens are hashed, bound to the email address, and consumed transactionally. They cannot be substituted for password-reset tokens. URL fragments are cleared from the address bar and are not included in server request URLs. Existing accounts start unverified after migration `0003`; their credentials, sessions, and workspaces are preserved. Verification records ownership only: this release does not require it for login, workflow creation, or provider usage.

## Models and sources

Provider keys are read only by backend processes. Set `OPENAI_API_KEY`/`OPENAI_MODEL`, `GEMINI_API_KEY`/`GEMINI_MODEL`, or the Ollama URL/model. OpenAI-compatible endpoints must implement the JSON chat-completions interface. Restart API and workers after changes. Compose maps `host.docker.internal` for an optional host Ollama server; install its selected model separately.

`SOURCE_HOSTS` is an operator-controlled exact-host allowlist. URL retrieval accepts HTTPS on port 443, rejects credentials and private/reserved addresses, pins a public DNS address, verifies TLS for the original hostname, revalidates redirects, and limits response size. It uses direct validated HTTPS connections; environments requiring all egress through a proxy need a reviewed equivalent transport. Uploading reference text/PDFs works without external retrieval.

PDF extraction uses a separate subprocess with memory, CPU, size, and page limits. Scanned-image OCR and encrypted PDFs are not supported.

## Operations and limits

### Database backups and restore checks

For the standard Compose deployment, create a new PostgreSQL custom archive:

```bash
# Local Compose stack:
python3 scripts/backup.py --output .data/backups/before-upgrade.dump
# Production stack instead:
python3 scripts/backup.py --production --output .data/backups/production-before-upgrade.dump
```

The command reads the selected stack's PostgreSQL database, checks the archive catalog, and prints its size and SHA-256 checksum. It creates the archive with owner-only permissions, refuses to replace an existing path, and removes partial files on failure. An archive becomes visible under its final name only after dumping and catalog validation succeed. New backup directories are private. Existing directories keep their permissions. Use a fresh filename for each manual backup. The scheduled runner below generates unique names and records checksums; retention remains operator-managed.

The archive contains application data, account/password hashes, saved sessions, extracted source text, and LangGraph checkpoints in the standard shared PostgreSQL database. It is not encrypted. Store protected, encrypted copies outside the server, and keep configuration/provider secrets and Caddy certificate state separately. Redis jobs, `.env` files, TLS state, external databases, and local SQLite files are not included. The script targets the standard project names and database/user from this repository; a customized or externally hosted database needs its own backup procedure.

`pg_dump` takes a consistent database snapshot without changing the source or stopping services. For an upgrade or recovery point with no in-flight application work, let workflows finish or reach human review, stop API/worker writes during the snapshot, then restart them. A readable archive catalog is not proof of recovery: the command explicitly returns `restore_verified: false`.

Test a restore into a disposable, isolated database. This example uses RAM for its data directory and is suitable for a small archive:

```bash
docker run -d --rm --name contentforge-restore-check --network none \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid \
  -e POSTGRES_USER=contentforge -e POSTGRES_DB=contentforge \
  -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine
docker exec contentforge-restore-check pg_isready -U contentforge -d contentforge
```

Once `pg_isready` reports that it is accepting connections, restore the archive and inspect application/checkpoint data:

```bash
docker exec -i contentforge-restore-check pg_restore \
  --username=contentforge --dbname=contentforge --no-owner --no-acl \
  --single-transaction --exit-on-error < .data/backups/before-upgrade.dump
docker exec contentforge-restore-check psql -U contentforge -d contentforge -X \
  -c 'SELECT count(*) AS campaigns FROM workflow_runs; SELECT count(*) AS checkpoints FROM checkpoints;'
docker stop contentforge-restore-check
```

The test database has no network access or published ports; its temporary data disappears when stopped. Check the saved checksum and inspect the restored records before treating a backup as usable. For actual recovery, restore into a fresh deployment database before starting application services, verify it, and retain the old deployment until recovery is confirmed. Redis queue state is separate: review unfinished workflows and their checkpoints before enabling workers. Never run this restore against a serving application database.

### Daily backup schedule and freshness checks

The scheduled runner builds on `scripts/backup.py`. It creates a unique UTC timestamped archive, a private JSON manifest containing its size/checksum/completion time, and an atomic latest-success pointer. A per-directory file lock prevents overlapping scheduled runners, including separate processes. Local and production stacks use separate filenames and latest-success pointers. The pointer is replaced only after the archive and manifest have been written successfully; failures before that step leave the previous pointer intact. Completed archives are preserved if a later metadata operation fails. A final directory-sync failure can report failure after the pointer was replaced, so use the read-only check to assess the referenced archive.

On the **deployment server**, using Python 3.11+ and the account that can already access Docker, first run a backup manually:

```bash
python3 scripts/scheduled_backup.py --production --directory "$PWD/.data/backups/scheduled-production"
python3 scripts/scheduled_backup.py --production --directory "$PWD/.data/backups/scheduled-production" --check
```

The destination must be a private directory owned by that account, with permissions `0700`. Missing directories are created privately. Existing directories are not chmodded; a shared or symlinked destination is rejected. Archives, manifests, pointers, and lock files must be private regular files owned by the same account. Existing backup files are never overwritten or automatically deleted. Do not edit a manifest or pointer to make a failed check pass.

Generate the user service and daily timer into a **new** output directory:

```bash
python3 scripts/configure_backup_schedule.py --production \
  --output-directory .data/backup-units \
  --backup-directory "$PWD/.data/backups/scheduled-production"
systemd-analyze verify .data/backup-units/*.service .data/backup-units/*.timer
cat .data/backup-units/contentforge-production-backup.service
cat .data/backup-units/contentforge-production-backup.timer
```

Generation only writes reviewable files; it never installs, starts, or enables a timer. Paths are resolved for the machine where you run the generator. Keep the checkout, Python interpreter, and backup directory in those locations, or regenerate/reinstall the units after moving them. Paths with internal spaces work; control characters, trailing spaces, quotes, backslashes, dollar signs, and percent signs are rejected. The default schedule is **02:00 UTC daily (07:30 India time)**, with up to ten minutes of randomized delay. Use `--hour-utc 4`, for example, to choose 04:00 UTC. `Persistent=true` requests one catch-up run after a missed schedule when the user manager becomes available.

After reviewing the generated files, install them on a Linux server with systemd user services. Preserve any previously installed units before replacing them:

```bash
install -d -m 700 "$HOME/.config/systemd/user"
install -m 600 .data/backup-units/contentforge-production-backup.service "$HOME/.config/systemd/user/"
install -m 600 .data/backup-units/contentforge-production-backup.timer "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user start contentforge-production-backup.service
systemctl --user enable --now contentforge-production-backup.timer
systemctl --user list-timers --all contentforge-production-backup.timer
journalctl --user -u contentforge-production-backup.service -n 30 --no-pager
```

The service account must retain Docker access and read access to the repository's private production configuration. For unattended operation after logout, the server administrator must enable lingering for that account using `loginctl enable-linger`. Verify the timer after reboot. A generated or syntax-validated timer is not proof that it is active. The cloud development workspace has no running systemd manager, so this release does not enable a timer there or on an external server. For local Compose, omit `--production`; the generated unit names are `contentforge-backup.service` and `.timer`.

A monitoring job can independently check freshness and the entire archive checksum:

```bash
python3 scripts/scheduled_backup.py --production \
  --directory "$PWD/.data/backups/scheduled-production" \
  --check --max-age-hours 26
```

Exit **0** reports a fresh, checksum-matching archive; exit **1** reports failure, with JSON output and redacted operational errors. Invalid CLI arguments use exit **2**. `--check` is read-only, makes no Docker/database calls, and reads the entire latest archive to verify its checksum. It rejects missing files, mismatched size/hash, invalid or cross-stack metadata, unsafe files/symlinks, future timestamps, and archives older than the threshold. The default threshold is 26 hours. A previous successful archive may still pass after a more recent backup attempt fails, until that archive becomes stale; use the service status and journal to inspect the latest attempt. No external notification is sent automatically.

The manifest is local integrity metadata, not a cryptographic signature. Neither successful creation nor a freshness check proves restoration: both retain `restore_verified: false`. Continue the isolated restore checks above. This setup does not encrypt or upload archives off-server, delete older copies, impose a disk quota, or back up configuration/TLS/Redis state. Monitor available disk space and apply a reviewed retention/off-server-copy policy. An abruptly killed process can leave hidden `.partial` files; these are never accepted as successful backups. A lost server can lose its on-server backups too.

### Workspace workflow allowances

`WORKFLOW_DAILY_LIMIT` defaults to **50 generation attempts per workspace per UTC day**. Each accepted new campaign, retry, or human revision request consumes one attempt across demo and live modes. Automatic agent retries and bounded quality revisions within that attempt do not consume additional attempts. Set the limit to **0** to pause new generation admissions while keeping editing, review, and downloads available. The accepted range is 0–100000.

`WORKFLOW_CONCURRENCY_LIMIT` defaults to **2 queued/running workflows per workspace**, with a range of 1–20. The same admission check applies to new campaigns, retries, requested revisions, and approval/export jobs. Waiting for human review releases the active slot. Approval does not consume the daily generation allowance, but still waits for an active slot. Rejection, editing, viewing, and downloading existing approved content remain available at either limit.

Set both values in `.env.production` for production Compose, the root `.env` for local Compose, or `backend/.env` for standalone development. Recreate/restart all API replicas with matching values. Lowering a limit does not terminate accepted work. Counts exceeding a newly lowered daily limit remain visible with zero remaining allowance. Zero daily allowance pauses generation admissions; it does not interrupt in-flight jobs.

**Settings → Workflow usage** reads persisted counts from the signed-in workspace, refreshes every 30 seconds while visible, and offers manual refresh. The daily reset is midnight UTC, displayed in the browser's local timezone. `GET /api/usage` requires authentication and never accepts a workspace selector. Limit denials return HTTP 429 with an explanatory message and `Retry-After`; form edits remain available for a later attempt.

Migration `0004` adds a per-workspace/day usage table. Back up PostgreSQL before upgrading. Existing accounts, campaigns, approvals, and checkpoints are preserved. Counters begin with admissions after the upgrade; historical runs are not charged retroactively. No scheduled reset task is needed. A workspace row lock serializes admission across PostgreSQL API replicas, and counters commit atomically with workflow transitions. Invalid requests and denied reviews roll back their counter changes. Accepted attempts remain charged after queue failures, workflow failures, or cancellation; retries consume a new attempt. Process restarts do not reset counts. Previous-day rows remain in the database and backups.

These are workflow admission limits, **not token budgets or currency spending caps**. Cancellation may leave a provider call running until it finishes, so the active-workflow count does not bound instantaneous external requests. Multiple accounts, guest accounts, internal agent retries, and automatic revisions can still add aggregate costs. Keep production registration and guest access closed, set provider-side spending controls, and add global abuse controls before admitting untrusted users. Existing queued work and jobs submitted directly by a trusted server operator are outside the API admission check.

### Service behavior

- Health: `GET /api/health` tests the database and, when configured, Redis. It does not certify a worker is consuming jobs or a model is reachable.
- The workspace header checks API health every 30 seconds while visible, on window focus, and on demand. Checks time out after five seconds. A lost browser connection or failed check replaces the available indicator; temporary identity lookup failures offer retry without starting a new guest session.
- Back up PostgreSQL, including checkpoint tables, and retain the root configuration separately. Local SQLite requires both the application database and checkpoint database.
- RQ jobs have a 30-minute limit. Worker failures are recorded as interrupted; the owner can resume from a checkpoint. A provider request already in flight may finish before cancellation is observed.
- Local mode uses one API process and a thread pool. Do not run multiple SQLite/local-queue replicas.
- Write and login throttles are process-local. Workspace workflow allowances are database-backed. Add trusted edge rate limiting, global spending controls, monitoring, and a shared store for request throttling before an Internet-facing multi-replica deployment.
- Authentication supports password accounts, SMTP password recovery, email verification, and per-account workspaces. SSO, shared-workspace roles, MFA, and a complete compliance program are not included.
- Production sign-up is closed by default; provision accounts from the server terminal. Public sign-up and guest creation still need aggregate abuse and spending controls if enabled; new workspaces each receive their own allowance. Closing sign-up does not revoke existing accounts or impose provider spending limits.
- Rich editor changes persist as plain text. External publishing and autonomous search are not implemented.

## Cloud environment

Use the existing `/workspace/Nikhil` checkout. Run `scripts/install.sh`, then `scripts/dev.sh`. Do not create a worktree for routine cloud tasks. Prepared files and dependencies can be snapshotted; running processes and open connections cannot. Re-run startup in new tasks and verify health plus a full demo campaign.

## Builds behind a trusted corporate proxy

If image builds need your organization’s CA bundle, keep TLS verification enabled and provide the existing trusted bundle as a build secret:

```bash
CONTENTFORGE_BUILD_CA=/path/to/trusted-ca-bundle.pem \
  docker compose -f compose.yaml -f compose.ca.yaml build
```

The optional override mounts the certificate bundle only during dependency installation; it is not committed or copied into images. If runtime provider traffic also requires that CA, supply the approved runtime trust bundle through the deployment secret/mount mechanism and configure `SSL_CERT_FILE`. Never use insecure TLS flags.

Run `python3 scripts/smoke.py` against a running local deployment to verify database access, task execution, evidence, human approval, and export. It requires demo sign-in enabled and creates a labeled verification project.
