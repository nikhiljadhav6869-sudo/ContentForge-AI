from datetime import datetime, timedelta, timezone


def latest_ids(run):
    return {
        max([v for v in run["versions"] if v["artifact_id"] == a["id"]], key=lambda v: v["number"])["id"]
        for a in run["artifacts"]
    }


def test_complete_demo_approval_export(client, campaign):
    run = campaign
    assert len(run["artifacts"]) == 4 and run["revision"] == 1
    assert {e["agent"] for e in run["executions"]} == {
        "supervisor",
        "research",
        "strategy",
        "writer",
        "fact_checker",
        "editor",
        "brand",
        "seo",
        "quality",
    }
    assert all(e["status"] == "completed" for e in run["executions"])
    assert client.get(f"/api/workflows/{run['id']}/export").status_code == 409
    assert any(c["status"] == "disputed" for c in run["claims"])
    assert any(c["status"] == "unverified" for c in run["claims"])
    assert all(c["status"] != "disputed" for c in run["claims"] if c["version_id"] in latest_ids(run))
    response = client.post(
        f"/api/workflows/{run['id']}/review",
        json={"decision": "approve", "acknowledge_warnings": True, "comment": "Reviewed the demo evidence."},
    )
    assert response.status_code == 200, response.text
    finished = client.get(f"/api/workflows/{run['id']}").json()
    assert finished["status"] == "completed", finished["error"]
    assert finished["executions"][-1]["agent"] == "export"
    exported = client.get(f"/api/workflows/{run['id']}/export")
    assert exported.status_code == 200 and "DEMO" in exported.text and "Evidence audit" in exported.text
    report = client.get(f"/api/workflows/{run['id']}/report").json()
    assert report["links"] and report["sources"] and report["reviews"]


def test_parallel_research_and_strategy(campaign):
    events = campaign["events"]
    start = {
        e["agent"]: e["sequence"]
        for e in events
        if e["type"] == "agent.started" and e["agent"] in ("research", "strategy")
    }
    completed = {
        e["agent"]: e["sequence"]
        for e in events
        if e["type"] == "agent.completed" and e["agent"] in ("research", "strategy")
    }
    assert max(start.values()) < min(completed.values())
    assert next(e["sequence"] for e in events if e["type"] == "agent.started" and e["agent"] == "writer") > max(
        completed.values()
    )


def test_evidence_integrity_and_multiple_sources(campaign):
    passages = {p["id"]: p for p in campaign["passages"]}
    versions = {v["id"]: v for v in campaign["versions"]}
    for link in campaign["links"]:
        assert link["quote"].casefold() in passages[link["passage_id"]]["text"].casefold()
    for claim in campaign["claims"]:
        assert versions[claim["version_id"]]["body"][claim["start"] : claim["end"]] == claim["text"]
        if claim["status"] == "supported":
            assert any(l["claim_id"] == claim["id"] and l["relation"] == "supports" for l in campaign["links"])
    claim = next(
        c for c in campaign["claims"] if c["text"] == "Battery electric vehicles produce no tailpipe emissions."
    )
    assert len([l for l in campaign["links"] if l["claim_id"] == claim["id"]]) >= 2


def test_contiguous_durable_events(campaign):
    events = campaign["events"]
    assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
    assert len({e["id"] for e in events}) == len(events)
    assert "revision.requested" in {e["type"] for e in events}
    cursor = events[len(events) // 2]["sequence"]
    assert next(e["sequence"] for e in events if e["sequence"] > cursor) == cursor + 1


def test_edits_reset_evidence_and_reject_stale_versions(client, campaign):
    artifact = campaign["artifacts"][0]
    old = max((v for v in campaign["versions"] if v["artifact_id"] == artifact["id"]), key=lambda v: v["number"])
    response = client.put(
        "/api/artifacts/" + artifact["id"],
        json={"body": old["body"] + "\n\nEvery battery lasts forever.", "base_version": old["number"]},
    )
    assert response.status_code == 200, response.text
    version = response.json()
    run = client.get("/api/workflows/" + campaign["id"]).json()
    assert version["number"] == old["number"] + 1
    claims = [c for c in run["claims"] if c["version_id"] == version["id"]]
    assert claims and all(c["status"] == "unverified" for c in claims)
    assert (
        client.put(
            "/api/artifacts/" + artifact["id"],
            json={"body": "Another document with a factual sentence.", "base_version": old["number"]},
        ).status_code
        == 409
    )
    assert client.post("/api/workflows/" + campaign["id"] + "/review", json={"decision": "approve"}).status_code == 409


def test_human_revision_and_rejection(client, campaign):
    assert (
        client.post(
            "/api/workflows/" + campaign["id"] + "/review",
            json={"decision": "revise", "comment": "Qualify lifecycle emissions."},
        ).status_code
        == 200
    )
    run = client.get("/api/workflows/" + campaign["id"]).json()
    assert run["cycle"] == 1 and run["status"] == "awaiting_approval"
    assert len(run["versions"]) > len(campaign["versions"])
    assert (
        client.post(
            "/api/workflows/" + campaign["id"] + "/review",
            json={"decision": "reject", "comment": "Needs external sources."},
        ).status_code
        == 200
    )
    assert client.get("/api/workflows/" + campaign["id"]).json()["status"] == "rejected"
    assert client.get("/api/workflows/" + campaign["id"] + "/export").status_code == 409


def test_cancel_blocks_approval(client, campaign):
    assert client.post("/api/workflows/" + campaign["id"] + "/cancel").status_code == 200
    assert client.get("/api/workflows/" + campaign["id"]).json()["status"] == "cancelled"
    assert (
        client.post(
            "/api/workflows/" + campaign["id"] + "/review", json={"decision": "approve", "acknowledge_warnings": True}
        ).status_code
        == 409
    )


def test_schedule_pins_approved_version(client, campaign):
    body = {
        "artifact_id": campaign["artifacts"][0]["id"],
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    assert client.post("/api/calendar", json=body).status_code == 409
    assert (
        client.post(
            "/api/workflows/" + campaign["id"] + "/review", json={"decision": "approve", "acknowledge_warnings": True}
        ).status_code
        == 200
    )
    result = client.post("/api/calendar", json=body)
    assert result.status_code == 201
    job = result.json()
    assert job["status"] == "scheduled_draft" and job["version_id"] in latest_ids(campaign)
    assert client.delete("/api/calendar/" + job["id"]).status_code == 200
    assert client.get("/api/calendar").json()[0]["status"] == "cancelled"


def test_comments_and_analytics(client, campaign):
    version = campaign["versions"][-1]
    assert (
        client.post(
            "/api/versions/" + version["id"] + "/comments",
            json={"text": "Check this sentence.", "quote": version["body"][:30]},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/versions/" + version["id"] + "/comments",
            json={"text": "A comment", "quote": "not in the document xyz"},
        ).status_code
        == 400
    )
    stats = client.get("/api/analytics").json()
    assert stats["projects"] == 1 and stats["artifacts"] == 4 and stats["pending"] == 1
    assert stats["supported_claims"] > 0
    assert all(a["estimated_cost"] is None for a in stats["agents"])


def test_durable_checkpoint_recovers_failed_stage(client, monkeypatch):
    import app.workflow as wf

    original = wf.demo_output

    def failing(agent, state):
        if agent == "writer":
            raise wf.ProviderError("Simulated writer outage")
        return original(agent, state)

    monkeypatch.setattr(wf, "demo_output", failing)
    run_id = client.post("/api/workflows", json={"prompt": "A campaign about electric vehicles in India."}).json()["id"]
    failed = client.get("/api/workflows/" + run_id).json()
    assert failed["status"] == "failed" and failed["executions"][-1]["status"] == "failed"
    monkeypatch.setattr(wf, "demo_output", original)
    assert client.post("/api/workflows/" + run_id + "/retry").status_code == 200
    recovered = client.get("/api/workflows/" + run_id).json()
    assert recovered["status"] == "awaiting_approval", recovered["error"]
    assert len([e for e in recovered["executions"] if e["agent"] == "supervisor"]) == 1
    assert recovered["retry_count"] == 1


def test_retry_is_bounded(client, monkeypatch):
    import app.workflow as wf

    def fail(agent, state):
        raise wf.ProviderError("Simulated outage")

    monkeypatch.setattr(wf, "demo_output", fail)
    run_id = client.post("/api/workflows", json={"prompt": "A campaign about electric vehicles."}).json()["id"]
    for _ in range(3):
        assert client.post("/api/workflows/" + run_id + "/retry").status_code == 200
    assert client.post("/api/workflows/" + run_id + "/retry").status_code == 409


def test_automatic_revision_limit(client):
    run_id = client.post(
        "/api/workflows", json={"prompt": "A campaign about electric vehicles.", "max_revisions": 0}
    ).json()["id"]
    run = client.get("/api/workflows/" + run_id).json()
    assert run["status"] == "awaiting_approval" and run["revision"] == 0 and len(run["quality"]) == 1


def test_human_evidence_link_and_quote_integrity(client, campaign):
    claim = next(
        c for c in campaign["claims"] if c["version_id"] in latest_ids(campaign) and c["status"] == "unverified"
    )
    passage = campaign["passages"][0]
    body = {
        "passage_id": passage["id"],
        "relation": "mentions",
        "quote": passage["text"][:70],
        "explanation": "The source mentions the general subject but does not prove this specific statement.",
    }
    result = client.post("/api/claims/" + claim["id"] + "/evidence", json=body)
    assert result.status_code == 201 and result.json()["status"] == "unverified"
    assert result.json()["history"][-2]["state"] == "re_evaluated"
    body["quote"] = "This quote was fabricated and does not appear in the passage."
    assert client.post("/api/claims/" + claim["id"] + "/evidence", json=body).status_code == 400


def test_negated_source_context_does_not_count_as_support(client):
    from app.db import Session, ContentArtifact
    from app.sources import store_source
    from app.traceability import new_version, verify_version
    from app.db import Project, ContentRequest, WorkflowRun

    who = client.get("/api/me").json()
    with Session.begin() as db:
        source = store_source(
            db, who["workspace_id"], "Negation reference", "It is false that all batteries last forever."
        )
        project = Project(workspace_id=who["workspace_id"], name="Evidence edge case")
        db.add(project)
        db.flush()
        request = ContentRequest(project_id=project.id, brief={})
        db.add(request)
        db.flush()
        run = WorkflowRun(project_id=project.id, request_id=request.id)
        db.add(run)
        db.flush()
        artifact = ContentArtifact(run_id=run.id, platform="blog", title="Test")
        db.add(artifact)
        db.flush()
        version = new_version(db, artifact, "All batteries last forever.", "Test")
        claims = verify_version(db, version, [source.id])
        assert claims and claims[0].status == "unverified"
