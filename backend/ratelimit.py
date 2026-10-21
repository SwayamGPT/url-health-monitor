import logging
import time
import uuid
from collections import defaultdict, deque

log = logging.getLogger(__name__)

# Sliding-window limiter as one atomic Lua script, so concurrent requests from
# several API workers can't both slip in under the limit.
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
if redis.call('ZCARD', key) >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    return math.ceil((tonumber(oldest[2]) + window - now) / 1000)
end
redis.call('ZADD', key, now, ARGV[4])
redis.call('PEXPIRE', key, window)
return 0
"""


class RateLimiter:
    """Allows `limit` calls per `window_seconds` per key.

    Uses Redis when REDIS_URL is configured (shared across workers/replicas), otherwise an
    in-process window that is only correct for a single worker. hit() returns 0 if allowed,
    else the number of seconds to wait."""

    def __init__(self, redis_url: str | None, limit: int, window_seconds: int = 60, prefix: str = "ratelimit"):
        self.limit = limit
        self.window_ms = window_seconds * 1000
        self.prefix = prefix
        self._redis = None
        self._script = None
        self._local: dict[str, deque] = defaultdict(deque)
        if redis_url:
            import redis.asyncio as redis
            self._redis = redis.from_url(redis_url)
            self._script = self._redis.register_script(_SLIDING_WINDOW_LUA)

    @property
    def backend(self) -> str:
        return "redis" if self._redis else "memory"

    async def hit(self, key: str) -> int:
        now_ms = int(time.time() * 1000)
        if self._redis:
            # Fail closed would take /ask down with Redis; fail open and log instead.
            try:
                return int(await self._script(
                    keys=[f"{self.prefix}:{key}"],
                    args=[now_ms, self.window_ms, self.limit, f"{now_ms}-{uuid.uuid4().hex}"],
                ))
            except Exception as e:
                log.warning("Redis rate limiter unavailable, allowing request: %s", e)
                return 0

        calls = self._local[key]
        while calls and now_ms - calls[0] >= self.window_ms:
            calls.popleft()
        if len(calls) >= self.limit:
            return max(1, -(-(calls[0] + self.window_ms - now_ms) // 1000))
        calls.append(now_ms)
        return 0

    async def close(self):
        if self._redis:
            await self._redis.aclose()
