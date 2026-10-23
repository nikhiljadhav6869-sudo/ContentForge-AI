from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def reminder(client, campaign):
    path = f"/api/workflows/{campaign['id']}"
    assert client.post(path + "/review", json={"decision": "approve", "acknowledge_warnings": True}).status_code == 200
    response = client.post(
        "/api/calendar",
        json={
            "artifact_id": campaign["artifacts"][0]["id"],
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


def move_body(reminder):
    return {
        "expected_scheduled_at": reminder["scheduled_at"],
        "scheduled_at": (datetime.now(timezone(timedelta(hours=5, minutes=30))) + timedelta(days=3)).isoformat(),
    }


def test_reschedule_preserves_approved_version_and_normalizes_timezone(client, reminder):
    before = client.get("/api/calendar").json()
    body = move_body(reminder)
    result = client.patch("/api/calendar/" + reminder["id"], json=body)
    assert result.status_code == 200
    moved = result.json()
    assert moved == {
        **reminder,
        "scheduled_at": datetime.fromisoformat(body["scheduled_at"]).astimezone(timezone.utc).isoformat(),
    }
    after = client.get("/api/calendar").json()
    assert len(after) == len(before) == 1
    assert after[0]["version_id"] == before[0]["version_id"]
    assert after[0]["scheduled_at"] == moved["scheduled_at"]


def test_reschedule_rejects_stale_edits_and_cancelled_reminders(client, reminder):
    path = "/api/calendar/" + reminder["id"]
    body = move_body(reminder)
    first = client.patch(path, json=body)
    assert first.status_code == 200
    before = client.get("/api/calendar").json()
    assert client.patch(path, json=body).status_code == 409
    assert client.get("/api/calendar").json() == before
    assert client.delete(path).status_code == 200
    body["expected_scheduled_at"] = first.json()["scheduled_at"]
    assert client.patch(path, json=body).status_code == 409
    assert client.get("/api/calendar").json()[0]["status"] == "cancelled"


def test_reschedule_enforces_ownership_and_authentication(client, reminder):
    path = "/api/calendar/" + reminder["id"]
    body = move_body(reminder)
    with TestClient(app) as other:
        assert other.patch(path, json=body).status_code == 401
        other.post("/api/auth/demo")
        assert other.patch(path, json=body).status_code == 404
        assert other.patch("/api/calendar/missing", json=body).status_code == 404
    assert client.get("/api/calendar").json()[0]["scheduled_at"] == reminder["scheduled_at"]


def test_reschedule_rejects_invalid_dates_and_changes_to_content(client, reminder):
    path = "/api/calendar/" + reminder["id"]
    before = client.get("/api/calendar").json()
    for date in ["", "not a date", "2000-01-01T10:00:00Z", "2099-01-01T10:00:00", "9999-12-31T23:59:59-23:00"]:
        assert client.patch(path, json={**move_body(reminder), "scheduled_at": date}).status_code == 400
    assert client.patch(path, json={"scheduled_at": move_body(reminder)["scheduled_at"]}).status_code == 422
    assert client.patch(path, json={**move_body(reminder), "version_id": "other-version"}).status_code == 422
    assert client.get("/api/calendar").json() == before


def test_reschedule_uses_cross_origin_write_protection(client, reminder):
    path = "/api/calendar/" + reminder["id"]
    body = move_body(reminder)
    before = client.get("/api/calendar").json()
    for headers in [{"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"}]:
        assert client.patch(path, json=body, headers=headers).status_code == 403
    assert client.get("/api/calendar").json() == before
    preflight = client.options(
        path,
        headers={
            "Origin": settings.frontend_origin,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert preflight.status_code == 200
    assert "PATCH" in preflight.headers["access-control-allow-methods"]
    assert client.patch(path, json=body, headers={"Origin": settings.frontend_origin}).status_code == 200
