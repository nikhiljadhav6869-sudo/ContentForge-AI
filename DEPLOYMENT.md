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

## Hosted frontend

The `frontend/` directory is compatible with a Next.js host such as Vercel. Set the root directory to `frontend`, install with `npm ci`, build with `npm run build`, and configure server-only `BACKEND_URL` **before the build**. It is used in the API rewrite. Do not put provider keys in `NEXT_PUBLIC_*` variables.

Deploy the backend separately on a persistent container service with PostgreSQL, Redis, and an RQ worker. Set `FRONTEND_ORIGIN` to the exact HTTPS frontend origin, `SECURE_COOKIES=true`, and `DEMO_AUTH=false`. If the hosting provider limits SSE duration, EventSource reconnects using the last event sequence. Proxies must preserve cookies, disable event-stream buffering/compression, and support streaming. A short HTTP timeout must not interrupt workflow workers.

No hosting account, DNS record, TLS certificate, or external publication integration is provisioned by this repository.

## Models and sources

Provider keys are read only by backend processes. Set `OPENAI_API_KEY`/`OPENAI_MODEL`, `GEMINI_API_KEY`/`GEMINI_MODEL`, or the Ollama URL/model. OpenAI-compatible endpoints must implement the JSON chat-completions interface. Restart API and workers after changes. Compose maps `host.docker.internal` for an optional host Ollama server; install its selected model separately.

`SOURCE_HOSTS` is an operator-controlled exact-host allowlist. URL retrieval accepts HTTPS on port 443, rejects credentials and private/reserved addresses, pins a public DNS address, verifies TLS for the original hostname, revalidates redirects, and limits response size. It uses direct validated HTTPS connections; environments requiring all egress through a proxy need a reviewed equivalent transport. Uploading reference text/PDFs works without external retrieval.

PDF extraction uses a separate subprocess with memory, CPU, size, and page limits. Scanned-image OCR and encrypted PDFs are not supported.

## Operations and limits

- Health: `GET /api/health` tests the database and, when configured, Redis. It does not certify a worker is consuming jobs or a model is reachable.
- The workspace header checks API health every 30 seconds while visible, on window focus, and on demand. Checks time out after five seconds. A lost browser connection or failed check replaces the available indicator; temporary identity lookup failures offer retry without starting a new guest session.
- Back up PostgreSQL, including checkpoint tables, and retain the root configuration separately. Local SQLite requires both the application database and checkpoint database.
- RQ jobs have a 30-minute limit. Worker failures are recorded as interrupted; the owner can resume from a checkpoint. A provider request already in flight may finish before cancellation is observed.
- Local mode uses one API process and a thread pool. Do not run multiple SQLite/local-queue replicas.
- Write and login throttles are process-local. Add trusted edge rate limiting, workload quotas, monitoring, and a shared limit store before an Internet-facing multi-replica deployment.
- Authentication supports password accounts and per-account workspaces. SSO, password reset, email verification, shared-workspace roles, MFA, and a complete compliance program are not included.
- Public sign-up and guest creation need operational quotas if enabled. Keep the demo local or disable guest sign-in.
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
