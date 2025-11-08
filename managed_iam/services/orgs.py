"""Organisation lifecycle service."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Mapping

from redis.asyncio import Redis

from managed_iam.crypto import EnvelopeCipher
from managed_iam.repos import OrgRecord, OrgRepository
from managed_iam.storage import RedisFactory

from managed_iam.config import settings


@dataclass
class OrgRegistrationResult:
    org_name: str
    api_key: str
    external_id: str


class OrganisationService:
    def __init__(self, redis: Redis | None = None) -> None:
        self._redis = redis or RedisFactory.client()
        self._repo = OrgRepository(self._redis)
        self._cipher = EnvelopeCipher(settings.decode_encryption_key())

    def _generate_secret(self, length: int = 32) -> str:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    async def register_org(self, *, org_name: str, owner_user_id: str) -> OrgRegistrationResult:
        api_key = self._generate_secret(40)
        external_id = self._generate_secret(48)
        await self._repo.create_org(org_name=org_name, owner_user_id=owner_user_id, api_key=api_key, external_id=external_id)
        return OrgRegistrationResult(org_name=org_name, api_key=api_key, external_id=external_id)

    async def verify_api_key(self, *, org_name: str, api_key: str) -> OrgRecord | None:
        return await self._repo.verify_api_key(org_name=org_name, api_key=api_key)

    async def get_org(self, org_name: str) -> OrgRecord | None:
        return await self._repo.get_org(org_name)

    async def mark_validated(
        self,
        org_name: str,
        *,
        account_id: str | None = None,
        account_partition: str | None = None,
        account_tags: Mapping[str, str] | None = None,
    ) -> None:
        await self._repo.mark_validated(
            org_name,
            account_id=account_id,
            account_partition=account_partition,
            account_tags=account_tags,
        )

    def decrypt_api_key(self, record: OrgRecord) -> str:
        return self._repo.decrypt_api_key(record)

    def decrypt_external_id(self, record: OrgRecord) -> str:
        return self._repo.decrypt_external_id(record)
