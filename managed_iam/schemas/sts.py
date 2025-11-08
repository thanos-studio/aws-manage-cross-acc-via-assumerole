"""STS credential request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _no_spaces(value: str) -> str:
    if " " in value:
        raise ValueError("must not contain spaces")
    return value


class CredentialsRequest(BaseModel):
    org_name: str
    target_account_id: str = Field(min_length=12, max_length=12)
    role_type: str = Field(pattern="^(readonly)$")
    api_key: str

    _validate_org = field_validator("org_name")(_no_spaces)


class CredentialsResponse(BaseModel):
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str
    console_url: str
    aws_cli_command: str
    template_url: str
    region: str
