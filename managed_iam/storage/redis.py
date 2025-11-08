"""Redis connection factory."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from redis.asyncio import Redis

from managed_iam.config import settings


class RedisFactory:
    """Provide reusable Redis asyncio connections."""

    _client: Redis | None = None
    _loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    def client(cls) -> Redis:
        current_loop: asyncio.AbstractEventLoop | None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if (
            cls._client is None
            or cls._loop is None
            or cls._loop.is_closed()
            or (current_loop is not None and cls._loop is not current_loop)
        ):
            cls._client = Redis.from_url(settings.redis_url, decode_responses=False)
            cls._loop = current_loop
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
