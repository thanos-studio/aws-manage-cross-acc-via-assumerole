"""Integration link schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _no_spaces(value: str) -> str:
    if " " in value:
        raise ValueError("must not contain spaces")
    return value


class IntegrationRequest(BaseModel):
    org_name: str = Field(..., min_length=3, max_length=32)
    api_key: str
    aws_profile: str | None = Field(default=None)
    expires_in: int = Field(default=3600, ge=300, le=43200)

    _validate_org = field_validator("org_name")(_no_spaces)


class IntegrationResponse(BaseModel):
    console_url: str
    aws_cli_command: str
    template_url: str
    region: str
