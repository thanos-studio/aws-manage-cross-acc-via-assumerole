"""Schemas for validating STS creds."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidateRequest(BaseModel):
    access_key_id: str
    secret_access_key: str
    session_token: str
    org_name: str = Field(..., min_length=3, max_length=32)
    api_key: str
    user_id: str
    region: str | None = None
    aws_profile: str | None = None


class ValidateResponse(BaseModel):
    success: bool
    identity_arn: str | None = None
    message: str
