import importlib.util
from pathlib import Path

import pytest

from app.config import settings
from app.gateway import availability, complete, ProviderError

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("space_start", ROOT / "deploy/space/start.py")
space = importlib.util.module_from_spec(spec)
spec.loader.exec_module(space)


def test_space_enforces_no_cost_services_and_private_data_settings():
    original = {
        "SPACE_HOST": "creator-contentforge-ai.hf.space", "OPENAI_API_KEY": "secret",
        "GEMINI_API_KEY": "secret", "REDIS_URL": "redis://external", "DEMO_ONLY": "false",
        "REGISTRATION_ENABLED": "true", "SMTP_HOST": "mail.example", "SMTP_PASSWORD": "secret",
        "DATABASE_URL": "postgresql://external", "PORT": "9999", "FORWARDED_ALLOW_IPS": "*",
    }
    result = space.environment(original)
    assert original["OPENAI_API_KEY"] == "secret"
    assert result["OPENAI_API_KEY"] == result["GEMINI_API_KEY"] == result["SMTP_HOST"] == ""
    assert result["SMTP_PASSWORD"] == result["REDIS_URL"] == result["CHECKPOINT_URL"] == ""
    assert result["DEMO_ONLY"] == result["DEMO_AUTH"] == result["SECURE_COOKIES"] == "true"
    assert result["REGISTRATION_ENABLED"] == "false"
    assert result["FRONTEND_ORIGIN"] == "https://creator-contentforge-ai.hf.space"
    assert result["DATABASE_URL"] == "sqlite:////app/data/contentforge.db"
    assert result["PORT"] == "7860" and result["FORWARDED_ALLOW_IPS"] == ""


@pytest.mark.parametrize("host", ["https://a.hf.space", "a.hf.space/evil", "a.example", "a.hf.space:443", "a.hf.space\n", "-a.hf.space"])
def test_invalid_space_host_is_rejected(host):
    with pytest.raises(ValueError):
        space.environment({"SPACE_HOST": host})


@pytest.mark.parametrize("origin", ["https://example.com", "http://evil.example:7860", "http://localhost:0", "http://localhost:65536"])
def test_local_origin_is_loopback_and_valid_port(origin):
    with pytest.raises(ValueError):
        space.environment({"DEMO_LOCAL_ORIGIN": origin})


def test_local_profile_allows_verification_without_tls():
    result = space.environment({"DEMO_LOCAL_ORIGIN": "http://localhost:7861"})
    assert result["FRONTEND_ORIGIN"] == "http://localhost:7861"
    assert result["SECURE_COOKIES"] == "false"


@pytest.mark.parametrize("provider", ["openai", "gemini", "ollama"])
def test_demo_only_cannot_call_provider_even_if_credentials_exist(monkeypatch, provider):
    monkeypatch.setattr(settings, "demo_only", True)
    monkeypatch.setattr(settings, "openai_api_key", "secret")
    monkeypatch.setattr(settings, "gemini_api_key", "secret")
    monkeypatch.setattr("app.gateway.httpx.Client", lambda *a, **kw: pytest.fail("Provider contacted"))
    assert availability() == {"demo": True, "openai": False, "gemini": False, "ollama": False}
    with pytest.raises(ProviderError, match="disabled"):
        complete(provider, "test", {})


def test_demo_only_api_exposes_profile_and_rejects_live_work(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_only", True)
    assert client.get("/api/settings").json()["demo_only"] is True
    for mode in ["openai", "gemini", "ollama"]:
        response = client.post("/api/workflows", json={"prompt": "Create a campaign about electric vehicles.", "mode": mode})
        assert response.status_code == 400
    assert client.get("/api/workflows").json() == []
