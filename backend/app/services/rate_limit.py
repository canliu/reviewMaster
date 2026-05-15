"""Redis-backed token bucket. Used to respect Amazon's per-developer-app
rate limits across all workers in this deployment.

The bucket key is shared across all users — Amazon rate-limits per developer
app, not per seller account. One global key per limit.
"""
from __future__ import annotations

import time

from redis import Redis

from app.core.queue import _redis_connection

# Lua script: read tokens + last refill timestamp, refill, attempt acquire.
# Atomic so concurrent workers can't double-spend a token.
_LUA = """
local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])  -- tokens per second
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last = tonumber(data[2])
if tokens == nil then tokens = max_tokens end
if last == nil then last = now end

local elapsed = math.max(0, now - last)
tokens = math.min(max_tokens, tokens + elapsed * refill_rate)

local granted = 0
if tokens >= 1 then
  tokens = tokens - 1
  granted = 1
end

redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
redis.call('EXPIRE', key, 60)
return granted
"""


class TokenBucket:
    def __init__(
        self,
        redis: Redis,
        key: str,
        *,
        max_tokens: float = 5,
        refill_rate: float = 1.0,
    ) -> None:
        self.redis = redis
        self.key = key
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self._script = redis.register_script(_LUA)

    def try_acquire(self) -> bool:
        granted = self._script(
            keys=[self.key],
            args=[self.max_tokens, self.refill_rate, time.time()],
        )
        return int(granted) == 1

    def acquire(self, *, timeout: float = 60.0, poll_interval: float = 0.1) -> bool:
        """Spin until a token is available or ``timeout`` elapses. Returns
        ``True`` on grant, ``False`` on timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.try_acquire():
                return True
            time.sleep(poll_interval)
        return False


# Shared bucket for the SP-API Solicitations endpoint (1/s steady, burst 5).
def solicitations_bucket() -> TokenBucket:
    return TokenBucket(
        _redis_connection(),
        "sp_api_solicitations:tokens",
        max_tokens=5,
        refill_rate=1.0,
    )
