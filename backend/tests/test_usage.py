from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app import main, usage
from app.config import Settings, settings
from app.db import ContentRequest, Project, Session, WorkflowRun, WorkspaceUsage
from app.schemas import Brief

BRIEF = {"prompt": "Create an evidence-led campaign about electric vehicles in India.", "mode": "demo"}


@pytest.fixture
def queue(client, monkeypatch):
    calls = []
    monkeypatch.setattr(main, "enqueue", lambda run_id, action="start": calls.append((run_id, action)))
    return calls


def launch(client):
    result = client.post("/api/workflows", json=BRIEF)
    assert result.status_code == 201, result.text
    return result.json()["id"]


def set_status(run_id, status):
    with Session.begin() as db:
        db.get(WorkflowRun, run_id).status = status


def test_usage_requires_identity_is_read_only_and_isolates_workspaces(client, queue):
    assert TestClient(main.app).get("/api/usage").status_code == 401
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(WorkspaceUsage)) == 0
    before = client.get("/api/usage").json()
    assert before["generation_attempts"] == before["active_workflows"] == 0
    with Session() as db:
        assert db.scalar(select(func.count()).select_from(WorkspaceUsage)) == 0
    launch(client)
    first = client.get("/api/me").json()["workspace_id"]
    other = TestClient(main.app)
    assert other.post("/api/auth/demo").status_code == 200
    assert other.get("/api/usage", params={"workspace_id": first}).json() == before
    assert client.get("/api/usage").json()["generation_attempts"] == 1


def test_daily_budget_counts_cancelled_attempts_and_blocks_without_creating_resources(client, queue, monkeypatch):
    monkeypatch.setattr(settings, "workflow_daily_limit", 2)
    for _ in range(2):
        run_id = launch(client)
        assert client.post(f"/api/workflows/{run_id}/cancel").status_code == 200
    with Session() as db:
        before = tuple(
            db.scalar(select(func.count()).select_from(model)) for model in (Project, ContentRequest, WorkflowRun)
        )
    blocked = client.post("/api/workflows", json=BRIEF)
    assert blocked.status_code == 429 and "Daily generation allowance" in blocked.json()["detail"]
    assert 0 < int(blocked.headers["Retry-After"]) <= 86400
    assert len(queue) == 2
    with Session() as db:
        assert (
            tuple(
                db.scalar(select(func.count()).select_from(model)) for model in (Project, ContentRequest, WorkflowRun)
            )
            == before
        )
    result = client.get("/api/usage").json()
    assert result["generation_attempts"] == 2 and result["remaining"] == result["active_workflows"] == 0


@pytest.mark.parametrize(
    "extra, code", [({"project_id": "missing"}, 404), ({"source_ids": ["missing"]}, 404), ({"mode": "openai"}, 400)]
)
def test_rejected_requests_do_not_charge(client, queue, monkeypatch, extra, code):
    monkeypatch.setattr(main, "availability", lambda: {"demo": True})
    assert client.post("/api/workflows", json={**BRIEF, **extra}).status_code == code
    assert client.get("/api/usage").json()["generation_attempts"] == 0
    assert queue == []


def test_retry_consumes_budget_and_rejected_retry_preserves_state(client, queue, monkeypatch):
    monkeypatch.setattr(settings, "workflow_daily_limit", 1)
    run_id = launch(client)
    set_status(run_id, "interrupted")
    assert client.post(f"/api/workflows/{run_id}/retry").status_code == 429
    with Session() as db:
        run = db.get(WorkflowRun, run_id)
        assert run.status == "interrupted" and run.retry_count == 0
    monkeypatch.setattr(settings, "workflow_daily_limit", 2)
    assert client.post(f"/api/workflows/{run_id}/retry").status_code == 200
    assert client.get("/api/usage").json()["generation_attempts"] == 2
    assert client.post(f"/api/workflows/{run_id}/retry").status_code == 409
    assert len(queue) == 2


def test_revision_budget_denial_rolls_back_review_and_approval_is_free(client, campaign, monkeypatch):
    monkeypatch.setattr(settings, "workflow_daily_limit", 1)
    path = f"/api/workflows/{campaign['id']}"
    before = client.get(path).json()
    denied = client.post(path + "/review", json={"decision": "revise", "comment": "Make it shorter."})
    assert denied.status_code == 429
    after = client.get(path).json()
    assert after["status"] == "awaiting_approval"
    assert after["cycle"] == before["cycle"] and after["reviews"] == before["reviews"]
    assert after["brief"] == before["brief"] and after["claims"] == before["claims"]
    assert client.post(path + "/review", json={"decision": "approve", "acknowledge_warnings": True}).status_code == 200
    assert client.get(path + "/export").status_code == 200
    assert client.get("/api/usage").json()["generation_attempts"] == 1


def test_valid_revision_is_charged_and_invalid_review_is_not(client, campaign, monkeypatch):
    calls = []
    monkeypatch.setattr(main, "enqueue", lambda *args: calls.append(args))
    path = f"/api/workflows/{campaign['id']}/review"
    assert client.post(path, json={"decision": "revise", "comment": " "}).status_code == 400
    assert client.get("/api/usage").json()["generation_attempts"] == 1
    assert client.post(path, json={"decision": "revise", "comment": "Make it shorter."}).status_code == 200
    assert client.get("/api/usage").json()["generation_attempts"] == 2
    assert len(calls) == 1


@pytest.mark.parametrize("action", ["approve", "revise", "retry"])
def test_active_limit_applies_to_every_resume_path_and_denials_rollback(client, campaign, monkeypatch, action):
    monkeypatch.setattr(main, "enqueue", lambda *args: None)
    monkeypatch.setattr(settings, "workflow_concurrency_limit", 1)
    active = launch(client)
    path = f"/api/workflows/{campaign['id']}"
    if action == "retry":
        set_status(campaign["id"], "failed")
        response = client.post(path + "/retry")
    else:
        response = client.post(
            path + "/review", json={"decision": action, "comment": "Revise this.", "acknowledge_warnings": True}
        )
    assert response.status_code == 429 and "active workflow limit" in response.json()["detail"]
    run = client.get(path).json()
    assert run["status"] == ("failed" if action == "retry" else "awaiting_approval")
    assert run["reviews"] == [] and run["cycle"] == run["retry_count"] == 0
    assert client.get("/api/usage").json()["generation_attempts"] == 2
    assert client.post("/api/workflows", json=BRIEF).status_code == 429
    assert client.post(f"/api/workflows/{active}/cancel").status_code == 200
    if action == "retry":
        assert client.post(path + "/retry").status_code == 200
    else:
        assert (
            client.post(
                path + "/review", json={"decision": action, "comment": "Revise this.", "acknowledge_warnings": True}
            ).status_code
            == 200
        )
    assert client.get("/api/usage").json()["generation_attempts"] == (2 if action == "approve" else 3)


def test_rejection_remains_available_with_no_daily_budget_and_all_active_slots_used(client, campaign, monkeypatch):
    monkeypatch.setattr(main, "enqueue", lambda *args: None)
    monkeypatch.setattr(settings, "workflow_concurrency_limit", 1)
    launch(client)
    monkeypatch.setattr(settings, "workflow_daily_limit", 0)
    assert client.post(f"/api/workflows/{campaign['id']}/review", json={"decision": "reject"}).status_code == 200
    assert client.get("/api/usage").json()["generation_attempts"] == 2


def test_queue_failure_remains_charged_and_zero_pauses_new_generation(client, monkeypatch):
    def fail(*args):
        raise RuntimeError("Queue unavailable")

    monkeypatch.setattr(main, "enqueue", fail)
    assert client.post("/api/workflows", json=BRIEF).status_code == 503
    assert client.get("/api/usage").json()["generation_attempts"] == 1
    monkeypatch.setattr(settings, "workflow_daily_limit", 0)
    result = client.get("/api/usage").json()
    assert result["remaining"] == 0 and result["generation_attempts"] == 1
    assert client.post("/api/workflows", json=BRIEF).status_code == 429


def test_utc_rollover_preserves_previous_day_and_read_does_not_reset_counters(client, queue, monkeypatch):
    moment = [datetime(2026, 10, 25, 23, 59, 59, tzinfo=timezone.utc)]
    monkeypatch.setattr(usage, "utc_now", lambda: moment[0])
    monkeypatch.setattr(settings, "workflow_daily_limit", 1)
    set_status(launch(client), "failed")
    blocked = client.post("/api/workflows", json=BRIEF)
    assert blocked.status_code == 429 and blocked.headers["Retry-After"] == "1"
    moment[0] = datetime(2026, 10, 26, tzinfo=timezone.utc)
    assert client.get("/api/usage").json()["remaining"] == 1
    launch(client)
    with Session() as db:
        assert [
            (r.day, r.generation_attempts) for r in db.scalars(select(WorkspaceUsage).order_by(WorkspaceUsage.day))
        ] == [("2026-10-25", 1), ("2026-10-26", 1)]


@pytest.mark.parametrize("daily, concurrent", [(1, 20), (50, 1)])
def test_simultaneous_starts_cannot_take_last_slot_twice(client, queue, monkeypatch, daily, concurrent):
    monkeypatch.setattr(settings, "workflow_daily_limit", daily)
    monkeypatch.setattr(settings, "workflow_concurrency_limit", concurrent)
    who = client.get("/api/me").json()

    def start(_):
        try:
            main.create_workflow(Brief(**BRIEF), who)
            return 201
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(start, range(2))) == [201, 429]
    assert client.get("/api/usage").json()["generation_attempts"] == 1
    assert len(queue) == 1


def test_start_and_retry_share_the_same_last_daily_allowance(client, queue, monkeypatch):
    run_id = launch(client)
    set_status(run_id, "failed")
    monkeypatch.setattr(settings, "workflow_daily_limit", 2)
    who = client.get("/api/me").json()

    def attempt(retry):
        try:
            if retry:
                main.retry(run_id, who)
            else:
                main.create_workflow(Brief(**BRIEF), who)
            return 200
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, [True, False])) == [200, 429]
    assert client.get("/api/usage").json()["generation_attempts"] == 2


@pytest.mark.parametrize(
    "values",
    [
        {"workflow_daily_limit": -1},
        {"workflow_daily_limit": 100001},
        {"workflow_concurrency_limit": 0},
        {"workflow_concurrency_limit": 21},
    ],
)
def test_invalid_limit_configuration_fails_closed(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_budget_is_shared_across_modes_and_cannot_be_overridden_in_request(client, queue, monkeypatch):
    monkeypatch.setattr(settings, "workflow_daily_limit", 1)
    monkeypatch.setattr(main, "availability", lambda: {"demo": True, "openai": True})
    result = client.post("/api/workflows", json={**BRIEF, "mode": "openai"})
    assert result.status_code == 201
    set_status(result.json()["id"], "failed")
    denied = client.post("/api/workflows", json={**BRIEF, "workflow_daily_limit": 1000, "workspace_id": "other"})
    assert denied.status_code == 429
    assert client.get("/api/usage").json()["daily_limit"] == 1
