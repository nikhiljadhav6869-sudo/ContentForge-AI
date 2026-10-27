"""Supervise the free demo's private API and public Next.js process."""

import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


def environment(source):
    host = source.get("SPACE_HOST", "")
    if host:
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.hf\.space", host):
            raise ValueError("SPACE_HOST must be the Space's direct hostname ending in .hf.space.")
        origin = "https://" + host
    else:
        # Loopback override is for local Docker verification only.
        origin = source.get("DEMO_LOCAL_ORIGIN", "http://localhost:7860")
        if not re.fullmatch(r"http://(?:localhost|127\.0\.0\.1):[0-9]{1,5}", origin):
            raise ValueError("Use SPACE_HOST for hosting, or a loopback DEMO_LOCAL_ORIGIN for local testing.")
        if not 1 <= int(origin.rsplit(":", 1)[1]) <= 65535:
            raise ValueError("Invalid local demo port.")
    result = dict(source)
    result.update(
        DATA_DIR="/app/data", DATABASE_URL="sqlite:////app/data/contentforge.db",
        CHECKPOINT_URL="", REDIS_URL="", FRONTEND_ORIGIN=origin,
        DEMO_ONLY="true", DEMO_AUTH="true", REGISTRATION_ENABLED="false",
        SECURE_COOKIES="true" if host else "false",
        WORKFLOW_DAILY_LIMIT="10", WORKFLOW_CONCURRENCY_LIMIT="1",
        OPENAI_API_KEY="", GEMINI_API_KEY="", SMTP_HOST="", SMTP_USERNAME="",
        SMTP_PASSWORD="", SMTP_FROM="", SOURCE_HOSTS="", FORWARDED_ALLOW_IPS="",
        HOSTNAME="0.0.0.0", PORT="7860", NODE_ENV="production",
    )
    return result


def stop(children):
    for child in children:
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 10
    for child in children:
        try:
            child.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()


def main():
    children = []

    def terminate(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        env = environment(os.environ)
        Path(env["DATA_DIR"]).mkdir(parents=True, exist_ok=True)

        def start(args, cwd):
            process = subprocess.Popen(args, cwd=cwd, env=env, start_new_session=True)
            children.append(process)
            return process

        migration = start(["alembic", "upgrade", "head"], "/app/backend")
        if migration.wait(timeout=120):
            raise RuntimeError("Database initialization failed.")
        api = start([
            "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--no-proxy-headers",
        ], "/app/backend")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if api.poll() is not None:
                raise RuntimeError("API exited during startup.")
            try:
                with opener.open("http://127.0.0.1:8000/api/health", timeout=2) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError("API did not become ready.")
        web = start(["node", "server.js"], "/app/web")
        print("Demo ready on port 7860. Live AI and email are disabled; export work before storage resets.", flush=True)
        while api.poll() is None and web.poll() is None:
            time.sleep(0.5)
        raise RuntimeError("An application process exited; stopping the demo container.")
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        print("Demo startup or process supervision failed. Check the container logs and SPACE_HOST setting.", file=sys.stderr)
        return 1
    finally:
        # Further termination signals must not interrupt cleanup of either service.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        stop(children)


if __name__ == "__main__":
    raise SystemExit(main())
