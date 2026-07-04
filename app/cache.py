from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Protocol

from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    pass


class BotCache(Protocol):
    async def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        ...

    async def append_context(self, group_id: str, message: str, limit: int = 20) -> None:
        ...

    async def get_context(self, group_id: str, limit: int = 10) -> list[str]:
        ...

    async def health(self) -> dict[str, str]:
        ...


@dataclass(slots=True)
class MemoryRateLimiter:
    buckets: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))
    contexts: dict[str, deque[str]] = field(default_factory=lambda: defaultdict(deque))

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        bucket = self.buckets[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise RateLimitExceeded(key)
        bucket.append(now)

    async def append_context(self, group_id: str, message: str, limit: int = 20) -> None:
        context = self.contexts[group_id]
        context.append(message)
        while len(context) > limit:
            context.popleft()

    async def get_context(self, group_id: str, limit: int = 10) -> list[str]:
        context = self.contexts[group_id]
        return list(context)[-limit:]

    async def health(self) -> dict[str, str]:
        return {"backend": "memory", "status": "ok"}


class RedisRateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        current = await self.redis.incr(key)
        if current == 1:
            await self.redis.expire(key, window_seconds)
        if current > limit:
            raise RateLimitExceeded(key)

    async def append_context(self, group_id: str, message: str, limit: int = 20) -> None:
        key = f"context:{group_id}"
        await self.redis.rpush(key, message)
        await self.redis.ltrim(key, -limit, -1)
        await self.redis.expire(key, 60 * 60 * 24)

    async def get_context(self, group_id: str, limit: int = 10) -> list[str]:
        key = f"context:{group_id}"
        values = await self.redis.lrange(key, -limit, -1)
        return [str(value) for value in values]

    async def health(self) -> dict[str, str]:
        await self.redis.ping()
        return {"backend": "redis", "status": "ok"}


async def create_rate_limiter(redis_url: str):
    if not redis_url:
        return MemoryRateLimiter()
    redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        await redis.ping()
    except Exception as exc:
        raise RuntimeError(f"Redis unavailable: {exc}") from exc
    return RedisRateLimiter(redis)
