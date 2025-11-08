"""Repository for organisation records."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Mapping, Optional

from redis.asyncio import Redis

from managed_iam.config import settings
from managed_iam.crypto import EnvelopeCipher, VerificationHash
from managed_iam.storage import RedisFactory

from .models import OrgRecord


ORG_KEY_TEMPLATE = "v1:orgs:{org_name}"
USER_ORG_KEY_TEMPLATE = "v1:users:{user_id}:orgs"


class OrgRepository:
    """Persist organisation metadata in Redis."""

    def __init__(self, redis: Optional[Redis] = None) -> None:
        self._redis = redis or RedisFactory.client()
        self._cipher = EnvelopeCipher(settings.decode_encryption_key())
        self._hasher = VerificationHash()

    async def create_org(self, *, org_name: str, owner_user_id: str, api_key: str, external_id: str) -> OrgRecord:
        key = ORG_KEY_TEMPLATE.format(org_name=org_name)
        exists = await self._redis.exists(key)
        if exists:
            raise ValueError("organisation already exists")

        api_key_cipher = self._cipher.encrypt(api_key.encode())
        external_cipher = self._cipher.encrypt(external_id.encode())
        api_key_hash = self._hasher.hash(api_key)

        payload = {
            b"owner_user_id": owner_user_id.encode(),
            b"api_key_cipher": base64.b64encode(api_key_cipher),
            b"api_key_hash": api_key_hash.encode(),
            b"external_id_cipher": base64.b64encode(external_cipher),
            b"validation_status": b"0",
            b"validation_updated_at": b"",
            b"account_id": b"",
            b"account_partition": b"",
            b"account_tags": b"",
        }
        await self._redis.hset(key, mapping=payload)
        await self._redis.sadd(USER_ORG_KEY_TEMPLATE.format(user_id=owner_user_id), org_name)

        return OrgRecord(
            org_name=org_name,
            owner_user_id=owner_user_id,
            api_key_cipher=api_key_cipher,
            api_key_hash=api_key_hash,
            external_id_cipher=external_cipher,
            validation_status=False,
            validation_updated_at=None,
            account_id=None,
            account_partition=None,
            account_tags=None,
        )

    async def get_org(self, org_name: str) -> OrgRecord | None:
        key = ORG_KEY_TEMPLATE.format(org_name=org_name)
        raw = await self._redis.hgetall(key)
        if not raw:
            return None

        validation_updated_at = (
            datetime.fromisoformat(raw[b"validation_updated_at"].decode()) if raw.get(b"validation_updated_at") else None
        )

        account_id_raw = raw.get(b"account_id")
        account_partition_raw = raw.get(b"account_partition")
        account_tags_raw = raw.get(b"account_tags")

        account_id = account_id_raw.decode() if account_id_raw else None
        if account_id == "":
            account_id = None

        account_partition = account_partition_raw.decode() if account_partition_raw else None
        if account_partition == "":
            account_partition = None

        account_tags = None
        if account_tags_raw:
            decoded = account_tags_raw.decode()
            if decoded:
                try:
                    obj = json.loads(decoded)
                    if isinstance(obj, dict):
                        account_tags = {str(k): str(v) for k, v in obj.items()}
                except json.JSONDecodeError:
                    account_tags = None

        return OrgRecord(
            org_name=org_name,
            owner_user_id=raw[b"owner_user_id"].decode(),
            api_key_cipher=base64.b64decode(raw[b"api_key_cipher"]),
            api_key_hash=raw[b"api_key_hash"].decode(),
            external_id_cipher=base64.b64decode(raw[b"external_id_cipher"]),
            validation_status=raw[b"validation_status"] == b"1",
            validation_updated_at=validation_updated_at,
            account_id=account_id,
            account_partition=account_partition,
            account_tags=account_tags,
        )

    async def verify_api_key(self, *, org_name: str, api_key: str) -> OrgRecord | None:
        record = await self.get_org(org_name)
        if not record:
            return None

        if not self._hasher.verify(api_key, record.api_key_hash):
            return None
        return record

    def decrypt_api_key(self, record: OrgRecord) -> str:
        return self._cipher.decrypt(record.api_key_cipher).decode()

    def decrypt_external_id(self, record: OrgRecord) -> str:
        return self._cipher.decrypt(record.external_id_cipher).decode()

    async def mark_validated(
        self,
        org_name: str,
        *,
        account_id: str | None = None,
        account_partition: str | None = None,
        account_tags: Mapping[str, str] | None = None,
    ) -> None:
        key = ORG_KEY_TEMPLATE.format(org_name=org_name)
        mapping: dict[str, str] = {
            "validation_status": "1",
            "validation_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if account_id is not None:
            mapping["account_id"] = account_id
        if account_partition is not None:
            mapping["account_partition"] = account_partition
        if account_tags is not None:
            mapping["account_tags"] = json.dumps(account_tags)
        await self._redis.hset(key, mapping=mapping)

    async def list_orgs_for_user(self, user_id: str) -> list[str]:
        members = await self._redis.smembers(USER_ORG_KEY_TEMPLATE.format(user_id=user_id))
        return sorted(member.decode() if isinstance(member, bytes) else member for member in members)
