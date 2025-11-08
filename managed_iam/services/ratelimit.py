"""Redis-backed rate limiting."""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.asyncio import Redis

from managed_iam.config import settings
from managed_iam.storage import RedisFactory


class RateLimitExceeded(Exception):
    """Raised when a subject exceeds configured rate limits."""


@dataclass
class RateLimiter:
    redis: Redis | None = None

    async def check(self, subject: str) -> None:
        client = self.redis or RedisFactory.client()
        window = settings.rate_limit_window_seconds
        bucket = int(time.time() // window)
        key = f"v1:ratelimit:{subject}:{bucket}"
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window)
        if count > settings.rate_limit_max_requests:
            raise RateLimitExceeded(f"rate limit exceeded for {subject}")
