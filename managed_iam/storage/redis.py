"""Redis connection factory."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.asyncio import Redis

from managed_iam.config import settings


class RedisFactory:
    """Provide Redis asyncio connections."""

    @classmethod
    def client(cls) -> Redis:
        return Redis.from_url(settings.redis_url, decode_responses=False)

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
