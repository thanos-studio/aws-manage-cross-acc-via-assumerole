"""User endpoint schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    metadata: dict[str, Any] | None = Field(default=None)


class UserCreateResponse(BaseModel):
    user_id: str = Field(description="Generated user identifier")
    metadata: dict[str, Any] | None = None

