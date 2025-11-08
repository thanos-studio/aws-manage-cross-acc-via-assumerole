"""Redis connection factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.asyncio import Redis

from managed_iam.config import settings


class RedisFactory:
    """Provide reusable Redis asyncio connections."""

    _client: Redis | None = None

    @classmethod
    def client(cls) -> Redis:
        if cls._client is None:
            cls._client = Redis.from_url(settings.redis_url, decode_responses=False)
        return cls._client

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None

    @classmethod
    @asynccontextmanager
    async def using(cls) -> AsyncIterator[Redis]:
        client = cls.client()
        try:
            yield client
        finally:
            # Keep connection alive (pooled), so no close here.
            pass

