from fastapi.testclient import TestClient

import app.main as main
from app.db import ContentRequest, Session, WorkflowRun
from app.main import app


def test_reusable_brief_is_read_only_and_scoped(client, campaign):
    path = f"/api/workflows/{campaign['id']}"
    with Session.begin() as db:
        run = db.get(WorkflowRun, campaign["id"])
        request = db.get(ContentRequest, run.request_id)
        request.brief = {**request.brief, "human_feedback": "Internal revision feedback", "project_id": run.project_id}
    before = client.get(path).json()
    count = len(client.get("/api/workflows").json())
    copied = client.get(path + "/brief")
    assert copied.status_code == 200
    brief = copied.json()
    assert "human_feedback" not in brief and "project_id" not in brief
    assert brief["source_ids"] == []  # Demo references are seeded on launch.
    assert brief["prompt"] == before["brief"]["prompt"]
    assert client.get(path).json() == before
    assert len(client.get("/api/workflows").json()) == count
    with TestClient(app) as other:
        assert other.get(path + "/brief").status_code == 401
        other.post("/api/auth/demo")
        assert other.get(path + "/brief").status_code == 404
        assert other.get("/api/workflows/missing/brief").status_code == 404


def test_copy_starts_fresh_without_changing_approved_original(client, campaign):
    path = f"/api/workflows/{campaign['id']}"
    assert client.post(path + "/review", json={"decision": "approve", "acknowledge_warnings": True}).status_code == 200
    before = client.get(path).json()
    brief = client.get(path + "/brief").json()
    brief.update(
        prompt="Create a new electric vehicle campaign for commuters.",
        audience="City commuters",
        platforms=["blog"],
        max_revisions=0,
    )
    result = client.post("/api/workflows", json=brief)
    assert result.status_code == 201
    copied = client.get("/api/workflows/" + result.json()["id"]).json()
    assert copied["id"] != before["id"]
    assert copied["project_id"] != before["project_id"]
    assert copied["status"] == "awaiting_approval"
    assert copied["reviews"] == []
    assert copied["brief"]["audience"] == "City commuters"
    assert {a["platform"] for a in copied["artifacts"]} == {"blog"}
    assert not ({v["id"] for v in copied["versions"]} & {v["id"] for v in before["versions"]})
    assert not (set(copied["brief"]["source_ids"]) & set(before["brief"]["source_ids"]))
    assert client.get("/api/workflows/" + copied["id"] + "/export").status_code == 409
    assert client.get(path).json() == before


def test_live_copy_preserves_sources_and_all_public_constraints(client, monkeypatch):
    # Queue only: no external model call or provider credentials needed.
    monkeypatch.setattr(main, "enqueue", lambda *args: None)
    monkeypatch.setattr(main, "availability", lambda: {"openai": True})
    source = client.post(
        "/api/sources/upload",
        files={"file": ("notes.txt", b"A reference with verifiable facts for the new campaign.", "text/plain")},
    ).json()
    brief = dict(
        prompt="Create a campaign using these uploaded notes.",
        audience="Researchers",
        tone="Precise and technical",
        goals="Explain the findings",
        brand="Careful language",
        platforms=["linkedin"],
        mode="openai",
        source_ids=[source["id"]],
        max_revisions=0,
        quality_threshold=93,
    )
    created = client.post("/api/workflows", json=brief)
    assert created.status_code == 201
    copied = client.get("/api/workflows/" + created.json()["id"] + "/brief")
    assert copied.status_code == 200
    assert copied.json() == brief
