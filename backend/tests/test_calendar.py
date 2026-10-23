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


def test_calendar_download_is_private_read_only_and_pins_the_version(client, reminder):
    before = client.get("/api/calendar").json()
    response = client.get("/api/calendar/" + reminder["id"] + "/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    assert (
        response.headers["content-disposition"] == f'attachment; filename="contentforge-reminder-{reminder["id"]}.ics"'
    )
    assert response.headers["cache-control"] == "no-store"
    text = response.content.decode("utf-8").replace("\r\n ", "")
    expected = datetime.fromisoformat(reminder["scheduled_at"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    assert f"DTSTART:{expected}\r\n" in text
    assert f"UID:{reminder['id']}@contentforge.local\r\n" in text
    assert "SUMMARY:[DEMO] Editorial reminder" in text
    assert reminder["version_id"] in text
    assert "No content is published automatically." in text
    assert "snapshot" in text and "CLASS:PRIVATE" in text
    assert "ATTENDEE:" not in text and "BEGIN:VALARM" not in text
    assert client.get("/api/calendar").json() == before


def test_calendar_download_uses_rescheduled_time_and_stable_uid(client, reminder):
    path = "/api/calendar/" + reminder["id"]
    original = client.get(path + "/export").content.decode().replace("\r\n ", "")
    body = move_body(reminder)
    assert client.patch(path, json=body).status_code == 200
    moved = client.get(path + "/export").content.decode().replace("\r\n ", "")
    expected = datetime.fromisoformat(body["scheduled_at"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    assert f"DTSTART:{expected}\r\n" in moved
    for key in ["UID:", "CREATED:", "DESCRIPTION:"]:
        assert next(line for line in original.split("\r\n") if line.startswith(key)) == next(
            line for line in moved.split("\r\n") if line.startswith(key)
        )


def test_calendar_download_rejects_other_accounts_and_cancelled_jobs(client, reminder):
    path = "/api/calendar/" + reminder["id"]
    with TestClient(app) as other:
        assert other.get(path + "/export").status_code == 401
        other.post("/api/auth/demo")
        assert other.get(path + "/export").status_code == 404
        assert other.get("/api/calendar/missing/export").status_code == 404
    assert client.delete(path).status_code == 200
    assert client.get(path + "/export").status_code == 409


def test_calendar_download_escapes_injection_and_folds_utf8_lines(client, reminder):
    from app.db import Session, ContentArtifact

    title = "नमस्ते 🌍 " * 25 + "\r\nBEGIN:VEVENT\rATTENDEE:mailto:fake@example.com\ncomma,semi;slash\\\x00"
    with Session.begin() as db:
        db.get(ContentArtifact, reminder["artifact_id"]).title = title
    result = client.get("/api/calendar/" + reminder["id"] + "/export")
    assert result.status_code == 200
    raw = result.content
    assert raw.endswith(b"\r\n")
    assert b"\n" not in raw.replace(b"\r\n", b"")
    for line in raw.split(b"\r\n"):
        assert len(line) <= 75
        line.decode("utf-8")  # A folded line must not split a multibyte character.
    unfolded = raw.decode().replace("\r\n ", "")
    lines = unfolded.split("\r\n")
    assert lines.count("BEGIN:VEVENT") == 1 and lines.count("END:VEVENT") == 1
    assert not any(line.startswith("ATTENDEE:") for line in lines)
    summary = next(line for line in lines if line.startswith("SUMMARY:"))
    assert "नमस्ते 🌍" in summary
    assert "\\nBEGIN:VEVENT\\nATTENDEE:" in summary
    assert "comma\\,semi\\;slash\\\\" in summary
    assert "\x00" not in unfolded


def test_live_calendar_download_has_no_demo_label(client, reminder):
    from app.db import Session, ContentArtifact, WorkflowRun

    # Exercise stored mode metadata without making an external model request.
    with Session.begin() as db:
        artifact = db.get(ContentArtifact, reminder["artifact_id"])
        db.get(WorkflowRun, artifact.run_id).mode = "openai"
    response = client.get("/api/calendar/" + reminder["id"] + "/export")
    assert response.status_code == 200
    assert "DEMO" not in response.text
