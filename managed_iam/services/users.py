"""Service for managing user identities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import shortuuid
from redis.asyncio import Redis

from managed_iam.storage import RedisFactory

USER_KEY_PREFIX = "v1:users"


@dataclass
class UserRecord:
    user_id: str
    metadata: dict[str, Any]


class UserService:
    def __init__(self, redis: Optional[Redis] = None) -> None:
        self._redis = redis or RedisFactory.client()

    async def create_user(self, metadata: Optional[dict[str, Any]] = None) -> UserRecord:
        user_id = shortuuid.ShortUUID().random(length=12)
        key = f"{USER_KEY_PREFIX}:{user_id}"
        await self._redis.hset(key, mapping={"active": "1"})
        if metadata:
            await self._redis.hset(key, mapping={f"meta:{k}": str(v) for k, v in metadata.items()})
        return UserRecord(user_id=user_id, metadata=metadata or {})

    async def ensure_user(self, user_id: str) -> bool:
        key = f"{USER_KEY_PREFIX}:{user_id}"
        exists = await self._redis.exists(key)
        return bool(exists)
