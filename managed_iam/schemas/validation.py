"""Schemas for validation webhook."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationWebhookPayload(BaseModel):
    org_name: str
    api_key: str
    account_id: str | None = Field(default=None)
    account_partition: str | None = Field(default=None)
    account_tags: dict[str, str] | None = Field(default=None)
    aws_profile: str | None = Field(default=None)


class ValidationWebhookResponse(BaseModel):
    org_name: str
    validated: bool
    account_id: str | None = Field(default=None)
    account_partition: str | None = Field(default=None)
    account_tags: dict[str, str] | None = Field(default=None)
