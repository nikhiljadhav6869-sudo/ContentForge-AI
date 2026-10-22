# Testing and recorded results

Validated on 22 October 2026 in the cloud workspace. These results describe this checkout; GitHub Actions has its own run history.

| Check | Result |
| --- | --- |
| Frozen installation, `./scripts/install.sh` | Passed: Python and npm dependencies, migrations, checkpoint initialization |
| Backend, `.venv/bin/pytest -q` | 31 passed |
| Python diagnostics, `.venv/bin/ruff check app tests` | Passed |
| Alembic schema drift check | No new upgrade operations detected |
| Frontend TypeScript check | Passed |
| Production Next.js build in Docker | Passed |
| npm dependency audit | 0 vulnerabilities reported at validation time |
| Playwright against the production web/API containers | 7 passed in 1.7 minutes, including ZIP downloads, saved export preferences, and account recovery |
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

`scripts/capture.mjs` captures real screenshots from a running demonstration. The checked-in screenshots were captured against the production containers.

## Coverage

Backend tests exercise the complete demo graph, parallel branch join, evidence/version integrity, source relationships, event sequencing, editing and stale versions, human approval/revision/rejection, cancellation, scheduling, comments, analytics, checkpoint recovery, bounded retries, ownership, cross-origin writes, upload/body limits, provider contracts, and error redaction. Provider adapters use mocked HTTP responses, including transient failure retries. Conservative evidence matching includes a negated-sentence regression.

Browser tests exercise the graph inspector, disputed evidence, editing and comments, approval, download, calendar, analytics, preferences, project/campaign creation, mobile navigation, responsive views at 390/768/1440 pixels, and SSE replay from a saved sequence cursor.

Recovery tests exercise failed health checks and successful retries, browser offline/reconnect events, temporary identity lookup failures, guest-session protection during an outage, failed sign-out, and switching to a new account without carrying over a campaign selection. Failure responses are intercepted in the browser; normal requests use the running API.

Export tests inspect ZIP contents, manifest checksums, reproducible downloads, Unicode text, safe archive paths, ownership, approved-version enforcement across all formats, and evidence relationships restricted to approved versions. The browser journey also downloads ZIP files and verifies that the saved export preference is used.

The container smoke test uses real PostgreSQL persistence, Redis dispatch, an RQ worker, and the PostgreSQL LangGraph checkpointer. It resumes a human-interrupted workflow and checks exported artifacts.

## Limits of validation

Live paid provider credentials were unavailable, and Ollama was not running; live generation is not verified against external models. General public website retrieval was not exhaustively tested. No public deployment, load test, independent penetration test, or social publishing integration was performed. Semantic claim extraction and quality scores are transparent heuristics, not certified fact checking. GitHub Actions is configured but its remote result must be checked separately.
