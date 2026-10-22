from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.sources import fetch_url
import pytest


def test_workspace_isolation(client, campaign):
    with TestClient(app) as other:
        assert other.get("/api/workflows/" + campaign["id"]).status_code == 401
        assert other.post("/api/auth/demo").status_code == 200
        assert other.get("/api/workflows/" + campaign["id"]).status_code == 404
        assert other.get("/api/workflows/" + campaign["id"] + "/report").status_code == 404
        assert (
            other.post(
                "/api/workflows",
                json={"prompt": "Try another workspace source", "source_ids": [campaign["sources"][0]["id"]]},
            ).status_code
            == 404
        )
        assert other.get("/api/analytics").json()["projects"] == 0


def test_registration_login_logout(client):
    body = {"email": "creator@example.com", "password": "a secure test password", "name": "Creator"}
    assert client.post("/api/auth/register", json=body).status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/auth/login", json={**body, "password": "incorrect-password"}).status_code == 401
    assert client.post("/api/auth/login", json=body).status_code == 200
    assert client.get("/api/me").json()["name"] == "Creator"
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_csrf_and_input_validation(client):
    assert (
        client.post("/api/projects", json={"name": "bad"}, headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    for body in [
        {"prompt": "short"},
        {"prompt": "A valid campaign prompt", "max_revisions": 100},
        {"prompt": "A valid campaign prompt", "platforms": []},
    ]:
        assert client.post("/api/workflows", json=body).status_code == 422


def test_safe_upload(client):
    result = client.post(
        "/api/sources/upload",
        files={"file": ("../../notes.txt", b"An uploaded reference with useful source information.", "text/plain")},
    )
    assert result.status_code == 201 and result.json()["title"] == "notes.txt"
    assert (
        client.post(
            "/api/sources/upload", files={"file": ("fake.pdf", b"not really a PDF", "application/pdf")}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/sources/upload", files={"file": ("bad.exe", b"pretend binary", "application/octet-stream")}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/sources/upload", files={"file": ("large.txt", b"x" * (2 * 1024 * 1024 + 1), "text/plain")}
        ).status_code
        == 413
    )


def test_private_source_destinations_blocked(monkeypatch):
    for url in [
        "http://www.iea.org/",
        "https://127.0.0.1/",
        "https://localhost/",
        "https://www.iea.org:444/",
        "https://user:pass@www.iea.org/",
        "file:///etc/passwd",
    ]:
        with pytest.raises(ValueError):
            fetch_url(url)
    monkeypatch.setattr("app.sources.socket.getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="Private"):
        fetch_url("https://www.iea.org/")


def test_no_credentials_in_browser_settings(client, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-secret-value")
    response = client.get("/api/settings")
    assert response.json()["providers"]["openai"] is True
    assert "test-secret-value" not in response.text and "openai_api_key" not in response.text


def test_settings_persist(client):
    prefs = client.get("/api/settings").json()["preferences"]
    prefs.update(brand_name="Acme", brand_voice="Clear and warm", theme="light", max_revisions=2)
    assert client.put("/api/settings", json=prefs).status_code == 200
    assert client.get("/api/settings").json()["preferences"] == prefs


def test_chunked_upload_body_limit(client):
    response = client.post(
        "/api/sources/text",
        content=iter([b"x" * (2 * 1024 * 1024 + 20001)]),
        headers={"content-type": "application/json", "transfer-encoding": "chunked"},
    )
    assert response.status_code == 413
