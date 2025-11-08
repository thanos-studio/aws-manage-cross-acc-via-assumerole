"""Handle validation webhook from managed Lambda."""

from __future__ import annotations

import json
from dataclasses import dataclass

from redis.asyncio import Redis

from managed_iam.crypto import HmacVerifier
from managed_iam.services.orgs import OrganisationService
from managed_iam.storage import RedisFactory

_NONCE_KEY_TEMPLATE = "v1:validation-nonce:{org}:{nonce}"


@dataclass
class ValidationResult:
    org_name: str
    validated: bool
    account_id: str | None = None
    account_partition: str | None = None
    account_tags: dict[str, str] | None = None


class ValidationWebhookService:
    def __init__(self, org_service: OrganisationService | None = None, redis: Redis | None = None) -> None:
        self._org_service = org_service or OrganisationService()
        self._redis = redis or RedisFactory.client()

    async def process_webhook(self, *, headers: dict[str, str], body: bytes) -> ValidationResult:
        signature = headers.get("x-sig-signature")
        timestamp_raw = headers.get("x-sig-timestamp")
        nonce = headers.get("x-sig-nonce")
        if not signature or not timestamp_raw or not nonce:
            raise ValueError("missing signature headers")
        if not nonce.strip():
            raise ValueError("nonce must be non-empty")

        try:
            timestamp = int(timestamp_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid signature timestamp") from exc

        payload = json.loads(body)
        org_name = payload["org_name"]
        supplied_api_key = payload.get("api_key")
        account_id = payload.get("account_id")
        account_partition = payload.get("account_partition")
        raw_tags = payload.get("account_tags")

        account_tags: dict[str, str] | None = None
        if raw_tags is not None:
            if not isinstance(raw_tags, dict):
                raise ValueError("account_tags must be an object")
            account_tags = {str(key): str(value) for key, value in raw_tags.items()}

        record = await self._org_service.get_org(org_name)
        if not record:
            raise ValueError("unknown organisation")

        stored_api_key = self._org_service.decrypt_api_key(record)
        if supplied_api_key != stored_api_key:
            raise ValueError("api key mismatch")

        verifier = HmacVerifier(secret=stored_api_key.encode())
        verifier.verify(body, provided_signature=signature, timestamp=timestamp, nonce=nonce)

        nonce_key = _NONCE_KEY_TEMPLATE.format(org=org_name, nonce=nonce)
        added = await self._redis.set(nonce_key, "1", nx=True, ex=verifier.tolerance_seconds)
        if not added:
            raise ValueError("nonce already used")

        await self._org_service.mark_validated(
            org_name,
            account_id=account_id,
            account_partition=account_partition,
            account_tags=account_tags,
        )
        return ValidationResult(
            org_name=org_name,
            validated=True,
            account_id=account_id,
            account_partition=account_partition,
            account_tags=account_tags,
        )
