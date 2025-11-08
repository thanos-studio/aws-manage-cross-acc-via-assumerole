"""Repository dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class OrgRecord:
    org_name: str
    owner_user_id: str
    api_key_cipher: bytes
    api_key_hash: str
    external_id_cipher: bytes
    validation_status: bool
    validation_updated_at: datetime | None
    account_id: str | None = None
    account_partition: str | None = None
    account_tags: dict[str, str] | None = None
