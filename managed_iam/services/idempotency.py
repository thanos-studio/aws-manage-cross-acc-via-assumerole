"""Simple Redis-backed idempotency enforcement."""

from __future__ import annotations

from redis.asyncio import Redis

from managed_iam.config import settings
from managed_iam.storage import RedisFactory


class IdempotencyError(Exception):
    """Raised when an idempotency key has already been used."""


class IdempotencyService:
    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis or RedisFactory.client()

    async def claim(self, key: str) -> None:
        redis_key = f"v1:idempotency:{key}"
        added = await self._redis.setnx(redis_key, "1")
        if not added:
            raise IdempotencyError("idempotency key already used")
        await self._redis.expire(redis_key, settings.idempotency_ttl_seconds)
