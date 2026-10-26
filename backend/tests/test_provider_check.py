import json

import pytest

from app import provider_check, gateway
from app.config import settings
from app.schemas import AgentOutput


@pytest.mark.parametrize("provider", ["openai", "gemini", "ollama"])
def test_probe_uses_real_gateway_contract_and_does_not_echo_output_or_configuration(monkeypatch, provider):
    monkeypatch.setattr(settings, "openai_api_key", "secret-sentinel")
    monkeypatch.setattr(settings, "gemini_api_key", "secret-sentinel")
    calls = []

    def complete(mode, instruction, context, on_retry):
        calls.append((mode, context))
        on_retry(1, "secret-sentinel")
        return AgentOutput(summary="secret-sentinel", data={"plan": ["draft"], "routing": "finish"}), {
            "input_tokens": 12,
            "output_tokens": 15,
            "model": "secret-sentinel",
        }

    monkeypatch.setattr(gateway, "complete", complete)
    result = provider_check.check_provider(provider)
    assert result["status"] == "passed" and result["live_generation_verified"]
    assert result["input_tokens"] == 12 and result["output_tokens"] == 15 and result["retries"] == 1
    assert calls[0][0] == provider and len(calls) == 1
    assert "secret-sentinel" not in json.dumps(result)


@pytest.mark.parametrize("provider", ["openai", "gemini"])
def test_missing_credentials_never_contact_provider(monkeypatch, provider):
    monkeypatch.setattr(settings, provider + "_api_key", "")
    monkeypatch.setattr(gateway, "complete", lambda *args, **kwargs: pytest.fail("Unexpected request"))
    result = provider_check.check_provider(provider)
    assert not result["configured"] and not result["live_generation_verified"]


@pytest.mark.parametrize("failure", ["exception", "schema", "empty"])
def test_failed_generation_or_invalid_schema_never_claims_success(monkeypatch, failure):
    def complete(*args, **kwargs):
        if failure == "exception":
            raise RuntimeError("secret-sentinel")
        return AgentOutput(summary="test", data={} if failure == "schema" else {"plan": [], "routing": ""}), {}

    monkeypatch.setattr(gateway, "complete", complete)
    result = provider_check.check_provider("ollama")
    assert result["status"] == "failed" and not result["live_generation_verified"]
    assert "secret-sentinel" not in json.dumps(result)


def test_cli_exit_codes_and_loading_errors_are_redacted(monkeypatch, capsys):
    def fail(provider):
        raise ValueError("secret-settings")

    monkeypatch.setattr(provider_check, "check_provider", fail)
    assert provider_check.main(["--provider", "openai"]) == 1
    assert "secret-settings" not in capsys.readouterr().out
    monkeypatch.setattr(provider_check, "check_provider", lambda provider: {"status": "passed"})
    assert provider_check.main(["--provider", "ollama"]) == 0
