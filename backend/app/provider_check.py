"""Send one small structured generation through the configured gateway; provider charges may apply."""

import argparse
import json
import time


def check_provider(provider):
    from .config import settings
    from .gateway import complete
    from .schemas import SupervisorData

    if provider not in {"openai", "gemini", "ollama"}:
        raise ValueError("Choose openai, gemini, or ollama.")
    configured = {
        "openai": bool(settings.openai_api_key.strip()),
        "gemini": bool(settings.gemini_api_key.strip()),
        "ollama": bool(settings.ollama_base_url.strip() and settings.ollama_model.strip()),
    }[provider]
    result = {
        "provider": provider,
        "status": "failed",
        "configured": configured,
        "live_generation_verified": False,
        "scope": "One structured response through the model gateway; no workflows, accounts, or email are created.",
        "not_verified": [
            "Full multi-agent workflow completion",
            "Factual accuracy",
            "Public deployment",
            "Provider spending limits",
        ],
    }
    if not configured:
        return {
            **result,
            "message": "Provider configuration is missing. Set its server-side credentials/model and retry.",
        }
    started = time.monotonic()
    retries = []
    try:
        output, metrics = complete(
            provider,
            'Return a concise test plan. data must be {"plan": ["research", "draft", "review"], "routing": "finish"}. Do not invoke tools or invent sources. Keep the response short.',
            {"task": "Check that the configured model can return the application's structured response."},
            on_retry=lambda attempt, reason: retries.append(attempt),
        )
        payload = SupervisorData.model_validate(output.data)
        if not payload.plan or not payload.routing.strip():
            raise ValueError("Empty structured result")
    except Exception:
        return {
            **result,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "retries": len(retries),
            "message": "Generation or structured-output validation failed. Check connectivity, credentials, model access, and quota. Raw provider details are omitted.",
        }
    tokens = {
        name: metrics.get(name) if type(metrics.get(name)) is int and metrics[name] >= 0 else None
        for name in ["input_tokens", "output_tokens"]
    }
    return {
        **result,
        "status": "passed",
        "live_generation_verified": True,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "retries": len(retries),
        **tokens,
        "message": "A live structured response passed validation. Review a full campaign next.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["openai", "gemini", "ollama"], required=True)
    args = parser.parse_args(argv)
    try:
        result = check_provider(args.provider)
    except Exception:
        result = {
            "status": "failed",
            "provider": args.provider,
            "live_generation_verified": False,
            "message": "Provider check could not load configuration. Raw settings and exception details are omitted.",
        }
    print(json.dumps(result))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
