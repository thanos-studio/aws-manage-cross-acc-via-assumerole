"""Utilities for integrating domain services with Django."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from managed_iam.storage import RedisFactory


@asynccontextmanager
async def redis_lifespan() -> AsyncIterator[None]:
    """Convenience context manager for ensuring Redis connections close cleanly."""
    try:
        yield
    finally:
        await RedisFactory.close()
