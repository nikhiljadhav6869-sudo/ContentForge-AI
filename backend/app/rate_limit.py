"""Shared sliding-window request admission; local fallback only without Redis configuration."""

from collections import deque
from functools import lru_cache
import hashlib
import ipaddress
import math
import threading
import time
from uuid import uuid4

from redis import Redis

from .config import settings

LIMITS = {"auth": 30, "write": 120}
WINDOW_SECONDS = 60

# One atomic operation across API replicas. Redis time avoids host-clock skew.
ADMIT = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) >= limit then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return math.max(1, math.ceil((tonumber(oldest[2]) + window - now) / 1000))
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], window)
return 0
"""


class LimiterUnavailable(RuntimeError):
    pass


def bucket_key(address, scope):
    # Collapse equivalent IPv6 spellings and IPv4-mapped addresses into one bucket.
    try:
        parsed = ipaddress.ip_address(address)
        address = str(getattr(parsed, "ipv4_mapped", None) or parsed)
    except ValueError:
        pass
    digest = hashlib.sha256(address.encode()).hexdigest()
    return f"contentforge:rate:v1:{scope}:{digest}"


@lru_cache(maxsize=4)
def redis_client(url):
    return Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2, max_connections=32)


class LocalLimiter:
    def __init__(self):
        self.buckets = {}
        self.lock = threading.Lock()

    def clear(self):
        with self.lock:
            self.buckets.clear()

    def check(self, key, limit):
        current = time.monotonic()
        with self.lock:
            if key not in self.buckets and len(self.buckets) >= 10000:
                for old in list(self.buckets):
                    if not self.buckets[old] or self.buckets[old][-1] <= current - WINDOW_SECONDS:
                        del self.buckets[old]
                if len(self.buckets) >= 10000:
                    raise LimiterUnavailable("Request admission is temporarily unavailable.")
            bucket = self.buckets.setdefault(key, deque())
            while bucket and bucket[0] <= current - WINDOW_SECONDS:
                bucket.popleft()
            if len(bucket) >= limit:
                return max(1, math.ceil(bucket[0] + WINDOW_SECONDS - current))
            bucket.append(current)
            return 0


local_limiter = LocalLimiter()


def check(address, scope):
    """Return zero on admission or a Retry-After delay. Never fall back during a Redis outage."""
    limit = LIMITS[scope]
    key = bucket_key(address, scope)
    if not settings.redis_url:
        return local_limiter.check(key, limit)
    try:
        delay = redis_client(settings.redis_url).eval(ADMIT, 1, key, WINDOW_SECONDS * 1000, limit, uuid4().hex)
        if type(delay) is not int or not 0 <= delay <= WINDOW_SECONDS:
            raise ValueError("Invalid limiter result")
        return delay
    except Exception:
        raise LimiterUnavailable("Request admission is temporarily unavailable.") from None
