from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import sys
from uuid import uuid4

import pytest
from redis import Redis

from app import rate_limit


def test_local_sliding_window_releases_exact_boundary(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: clock[0])
    limiter = rate_limit.LocalLimiter()
    assert limiter.check("one", 2) == 0
    clock[0] = 101
    assert limiter.check("one", 2) == 0
    assert limiter.check("one", 2) == 59
    assert limiter.check("other", 2) == 0
    clock[0] = 160
    assert limiter.check("one", 2) == 0
    assert limiter.check("one", 2) == 1
    clock[0] = 161
    assert limiter.check("one", 2) == 0


def test_local_concurrent_admission_and_bounded_storage(monkeypatch):
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 100)
    limiter = rate_limit.LocalLimiter()
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: limiter.check("same", 30), range(80)))
    assert results.count(0) == 30
    limiter.buckets = {str(i): deque([100]) for i in range(10000)}
    with pytest.raises(rate_limit.LimiterUnavailable):
        limiter.check("new", 30)
    assert len(limiter.buckets) == 10000
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: 160)
    assert limiter.check("new", 30) == 0
    assert len(limiter.buckets) == 1


def test_equivalent_addresses_and_scopes():
    assert rate_limit.bucket_key("::ffff:192.0.2.1", "auth") == rate_limit.bucket_key("192.0.2.1", "auth")
    assert rate_limit.bucket_key("2001:0db8::1", "auth") == rate_limit.bucket_key("2001:db8::1", "auth")
    assert rate_limit.bucket_key("192.0.2.1", "auth") != rate_limit.bucket_key("192.0.2.1", "write")
    assert "192.0.2.1" not in rate_limit.bucket_key("192.0.2.1", "auth")


@pytest.mark.parametrize("result", [0, 1, 60])
def test_redis_arguments_and_results(monkeypatch, result):
    monkeypatch.setattr(rate_limit.settings, "redis_url", "redis://synthetic")
    calls = []

    class Client:
        def eval(self, *args):
            calls.append(args)
            return result

    monkeypatch.setattr(rate_limit, "redis_client", lambda _: Client())
    assert rate_limit.check("192.0.2.1", "auth") == result
    assert calls[0][:5] == (rate_limit.ADMIT, 1, rate_limit.bucket_key("192.0.2.1", "auth"), 60000, 30)
    assert len(calls[0][5]) == 32


@pytest.mark.parametrize("failure", [None, -1, 61, "0", True, OSError("secret-redis-password")])
def test_redis_failure_is_redacted_and_never_falls_back(monkeypatch, failure):
    monkeypatch.setattr(rate_limit.settings, "redis_url", "redis://synthetic")

    class Client:
        def eval(self, *args):
            if isinstance(failure, Exception):
                raise failure
            return failure

    monkeypatch.setattr(rate_limit, "redis_client", lambda _: Client())
    monkeypatch.setattr(rate_limit.local_limiter, "check", lambda *a: pytest.fail("Fell back locally"))
    with pytest.raises(rate_limit.LimiterUnavailable) as error:
        rate_limit.check("192.0.2.1", "write")
    assert "secret" not in str(error.value)


def test_http_limits_retry_after_scope_and_untrusted_forwarding(client, monkeypatch):
    rate_limit.local_limiter.clear()
    monkeypatch.setitem(rate_limit.LIMITS, "auth", 2)
    for spoof in ["192.0.2.1", "192.0.2.2"]:
        assert client.post("/api/auth/login", json={}, headers={"X-Forwarded-For": spoof}).status_code == 422
    denied = client.post("/api/auth/login", json={}, headers={"X-Forwarded-For": "192.0.2.3"})
    assert denied.status_code == 429
    assert 1 <= int(denied.headers["retry-after"]) <= 60
    assert denied.headers["cache-control"] == "no-store"
    assert client.post("/api/not-a-route").status_code == 404
    assert client.get("/api/settings").status_code == 200


def test_http_limiter_outage_blocks_mutations_but_not_reads(client, monkeypatch):
    def unavailable(*args):
        raise rate_limit.LimiterUnavailable()

    monkeypatch.setattr(rate_limit, "check", unavailable)
    denied = client.post("/api/auth/logout")
    assert denied.status_code == 503 and denied.headers["retry-after"] == "5"
    assert client.get("/api/me").status_code == 200  # Logout was not executed.
    assert client.post("/api/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403


@pytest.fixture
def shared_redis(monkeypatch):
    url = os.environ.get("CONTENTFORGE_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set CONTENTFORGE_TEST_REDIS_URL for real Redis integration checks")
    client = Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
    client.ping()
    address = "test-" + uuid4().hex
    monkeypatch.setattr(rate_limit.settings, "redis_url", url)
    try:
        yield client, address, url
    finally:
        client.delete(*(rate_limit.bucket_key(address, scope) for scope in ["auth", "write"]))
        client.close()


def test_real_redis_window_ttl_and_scope(shared_redis):
    client, address, _ = shared_redis
    key = rate_limit.bucket_key(address, "auth")
    assert [rate_limit.check(address, "auth") for _ in range(30)] == [0] * 30
    assert 1 <= rate_limit.check(address, "auth") <= 60
    assert client.zcard(key) == 30
    assert 0 < client.pttl(key) <= 60000
    assert rate_limit.check(address, "write") == 0
    seconds, micros = client.time()
    expired = seconds * 1000 + micros // 1000 - 60001
    client.zadd(key, {member: expired for member in client.zrange(key, 0, -1)})
    assert rate_limit.check(address, "auth") == 0
    assert client.zcard(key) == 1


def test_real_redis_admission_shared_across_processes(shared_redis):
    client, address, url = shared_redis
    script = """
import json, sys
from app.rate_limit import check
results = [check(sys.argv[1], 'auth') for _ in range(12)]
print(json.dumps({'admitted': results.count(0), 'denied': sum(x > 0 for x in results)}))
"""

    def process(_):
        result = subprocess.run(
            [sys.executable, "-c", script, address], env={**os.environ, "REDIS_URL": url},
            capture_output=True, text=True, timeout=30, check=True,
        )
        return json.loads(result.stdout)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(process, range(4)))
    assert sum(x["admitted"] for x in results) == 30
    assert sum(x["denied"] for x in results) == 18
    assert client.zcard(rate_limit.bucket_key(address, "auth")) == 30
    # A new client/process cannot reset the accepted attempts.
    assert process(0) == {"admitted": 0, "denied": 12}
