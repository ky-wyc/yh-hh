from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    pass


@dataclass(slots=True)
class MemoryRateLimiter:
    buckets: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        bucket = self.buckets[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise RateLimitExceeded(key)
        bucket.append(now)


class RedisRateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, window_seconds)
        if current > limit:
            raise RateLimitExceeded(key)


async def create_rate_limiter(redis_url: str):
    if not redis_url:
        return MemoryRateLimiter()
    redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        await redis.ping()
    except Exception as exc:
        raise RuntimeError(f"Redis unavailable: {exc}") from exc
    return RedisRateLimiter(redis)

