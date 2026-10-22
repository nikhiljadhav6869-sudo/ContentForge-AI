import httpx
import pytest
from app.gateway import complete, ProviderError
from app.config import settings


class FakeClient:
    responses = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def post(self, *args, **kwargs):
        return self.responses.pop(0)


def test_openai_usage_and_rate_limit_retry(monkeypatch):
    monkeypatch.setattr("app.gateway.httpx.Client", FakeClient)
    monkeypatch.setattr("app.gateway.time.sleep", lambda _: None)
    monkeypatch.setattr(settings, "input_cost_per_million", 1.0)
    monkeypatch.setattr(settings, "output_cost_per_million", 2.0)
    FakeClient.responses = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"summary":"Planned campaign","data":{},"warnings":[]}'},
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        ),
    ]
    retries = []
    result, metrics = complete("openai", "Plan a campaign", {}, lambda *args: retries.append(args))
    assert result.summary == "Planned campaign"
    assert metrics["input_tokens"] == 100 and metrics["output_tokens"] == 50 and metrics["retries"] == 1
    assert metrics["estimated_cost"] == 0.0002 and len(retries) == 1


def test_provider_error_redacts_response_body(monkeypatch):
    monkeypatch.setattr("app.gateway.httpx.Client", FakeClient)
    FakeClient.responses = [httpx.Response(401, text="secret-provider-error-content")]
    with pytest.raises(ProviderError) as error:
        complete("openai", "Test", {})
    assert "secret-provider-error-content" not in str(error.value)


def test_gemini_and_ollama_adapters(monkeypatch):
    monkeypatch.setattr("app.gateway.httpx.Client", FakeClient)
    result = '{"summary":"Draft prepared","data":{},"warnings":[]}'
    FakeClient.responses = [
        httpx.Response(
            200,
            json={
                "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": result}]}}],
                "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 20},
            },
        )
    ]
    assert complete("gemini", "Test", {})[1]["input_tokens"] == 12
    FakeClient.responses = [
        httpx.Response(200, json={"message": {"content": result}, "prompt_eval_count": 13, "eval_count": 21})
    ]
    assert complete("ollama", "Test", {})[1]["output_tokens"] == 21


def test_incomplete_or_invalid_structured_output_rejected(monkeypatch):
    monkeypatch.setattr("app.gateway.httpx.Client", FakeClient)
    for choice in [
        {"finish_reason": "length", "message": {"content": "{}"}},
        {"finish_reason": "stop", "message": {"content": "not JSON"}},
    ]:
        FakeClient.responses = [httpx.Response(200, json={"choices": [choice]})]
        with pytest.raises(ProviderError):
            complete("openai", "Test", {})
