from __future__ import annotations

from app.cache import MemoryRateLimiter, RedisRateLimiter


class FakeRedis:
    def __init__(self):
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


async def test_memory_rate_limiter_close_is_noop():
    limiter = MemoryRateLimiter()

    await limiter.close()


async def test_redis_rate_limiter_close_closes_client():
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis)  # type: ignore[arg-type]

    await limiter.close()

    assert redis.closed is True
