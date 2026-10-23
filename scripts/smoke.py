"""Exercise a running deployment without printing credentials or session cookies."""

import argparse
import getpass
import hashlib
import http.cookiejar
import io
import json
import os
import ssl
import time
import urllib.request
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument("--base-url", default="http://localhost:3000")
parser.add_argument(
    "--email", help="Sign in to an existing account instead of creating a guest session"
)
parser.add_argument(
    "--ca-file",
    help="Trusted CA bundle for an HTTPS test deployment; TLS verification stays enabled",
)
args = parser.parse_args()
base = args.base_url.rstrip("/")
client = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    urllib.request.HTTPSHandler(
        context=ssl.create_default_context(cafile=args.ca_file)
    ),
)


def request(path, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + "/api" + path,
        data=data,
        headers={"Content-Type": "application/json", "Origin": base},
    )
    with client.open(req, timeout=30) as response:
        return response.read() if raw else json.load(response)


def wait_for(run_id, target):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        run = request("/workflows/" + run_id)
        if run["status"] == target:
            return run
        if run["status"] in ("failed", "interrupted", "cancelled"):
            raise RuntimeError(run["error"])
        time.sleep(0.5)
    raise RuntimeError("Workflow did not reach " + target)


health = request("/health")
assert health["status"] == "ok"
if args.email:
    password = os.environ.get("CONTENTFORGE_SMOKE_PASSWORD") or getpass.getpass(
        "Account password: "
    )
    request("/auth/login", {"email": args.email, "password": password})
    del password
else:
    request("/auth/demo", {})
project = request("/projects", {"name": "Deployment verification"})
run_id = request(
    "/workflows",
    {
        "project_id": project["id"],
        "prompt": "Create a researched content campaign about electric vehicles in India.",
        "mode": "demo",
    },
)["id"]
run = wait_for(run_id, "awaiting_approval")
assert len(run["artifacts"]) == 4 and run["revision"] == 1
assert run["links"] and any(c["status"] == "disputed" for c in run["claims"])
request(
    "/workflows/" + run_id + "/review",
    {
        "decision": "approve",
        "acknowledge_warnings": True,
        "comment": "Deployment smoke test reviewed demo fixtures.",
    },
)
finished = wait_for(run_id, "completed")
last_event = finished["events"][-1]
event_request = urllib.request.Request(
    base + "/api/workflows/" + run_id + "/events",
    headers={"Last-Event-ID": str(last_event["sequence"] - 1)},
)
with client.open(event_request, timeout=10) as response:
    assert response.headers.get_content_type() == "text/event-stream"
    while True:
        line = response.readline().decode()
        if not line:
            raise RuntimeError("Event stream closed before replaying the saved event.")
        if line.startswith("data: "):
            assert json.loads(line[6:])["sequence"] == last_event["sequence"]
            break
exported = request("/workflows/" + run_id + "/export?format=json")
assert len(exported["artifacts"]) == 4 and exported["approval"]["decision"] == "approve"
package = request("/workflows/" + run_id + "/export?format=zip", raw=True)
with zipfile.ZipFile(io.BytesIO(package)) as archive:
    manifest = json.loads(archive.read("manifest.json"))
    assert {item["version_id"] for item in manifest["artifacts"]} == set(
        exported["approval"]["version_ids"]
    )
    assert json.loads(archive.read("campaign.json")) == exported
    for entry in manifest["files"]:
        content = archive.read(entry["path"])
        assert (
            len(content) == entry["bytes"]
            and hashlib.sha256(content).hexdigest() == entry["sha256"]
        )
    zip_files = len(archive.namelist())
print(
    json.dumps(
        {
            "status": "passed",
            "database": health["database"],
            "queue": health["queue"],
            "agents": len({e["agent"] for e in finished["executions"]}),
            "events": len(finished["events"]),
            "artifacts": len(exported["artifacts"]),
            "zip_files": zip_files,
            "event_replay": "passed",
            "run_id": run_id,
        }
    )
)
