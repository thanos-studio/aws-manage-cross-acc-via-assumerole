"""Organisation endpoint schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _no_spaces(value: str) -> str:
    if " " in value:
        raise ValueError("must not contain spaces")
    return value


class OrgRegisterRequest(BaseModel):
    org_name: str = Field(..., min_length=3, max_length=32)

    _validate_spaces = field_validator("org_name")(_no_spaces)


class OrgRegisterResponse(BaseModel):
    org_name: str
    api_key: str
    external_id: str

