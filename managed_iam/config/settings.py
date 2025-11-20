"""Application settings using Pydantic settings management."""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, RootModel, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CorsOrigins(RootModel[List[AnyHttpUrl]]):
    """Model wrapper to allow list of HTTP URLs."""


class Settings(BaseSettings):
    """Environment configuration for the Managed IAM prototype."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", env_prefix="SUNRIN_")

    app_name: str = Field(default="sunrin-managed-iam-prototype")
    environment: str = Field(default="dev")

    redis_url: str = Field(default="redis://localhost:6379/0")

    encryption_key: str = Field(
        ...,
        description="Base64 encoded 256-bit key for AES-GCM encryption.",
    )
    hmac_key: str = Field(
        ...,
        description="Base64 encoded key used for validation webhook HMAC signatures.",
    )

    provider_account_id: str = Field(default="628897991799")
    provider_readonly_role: str = Field(default="SunrinPowerUser")
    aws_region: str = Field(default="us-east-1")
    template_bucket: str = Field(
        ..., description="S3 bucket where CloudFormation templates are stored via public pre-signed URLs."
    )
    template_key: str = Field(
        default="stack.yaml",
        description="Object key for the primary IAM CloudFormation template.",
    )
    template_public_access: bool = Field(
        default=False,
        description="Set true when the template bucket/object is already public, so no presign is required.",
    )

    validation_endpoint_base: AnyHttpUrl = Field(default="https://test.sunrin.us")

    cors_origins: Optional[CorsOrigins] = None

    log_bucket_tag_key: str = Field(default="Managed")
    log_bucket_tag_value: str = Field(default="Sunrin")

    session_name_format: str = Field(default="Sunrin-{org_name}-{user_id}")

    rate_limit_window_seconds: int = Field(default=60)
    rate_limit_max_requests: int = Field(default=10)
    idempotency_ttl_seconds: int = Field(default=3600)
    django_debug: bool = Field(
        default=False,
        description="Mirror Django's DEBUG flag so both settings derive from the same env var.",
    )

    def decode_encryption_key(self) -> bytes:
        import base64

        return base64.b64decode(self.encryption_key)

    def decode_hmac_key(self) -> bytes:
        import base64

        return base64.b64decode(self.hmac_key)

    @model_validator(mode="after")
    def validate_crypto_material(self) -> "Settings":
        encryption_len = len(self.decode_encryption_key())
        if encryption_len not in {16, 24, 32}:
            raise ValueError("SUNRIN_ENCRYPTION_KEY must decode to 16, 24, or 32 bytes (128/192/256-bit).")

        if len(self.decode_hmac_key()) < 32:
            raise ValueError("SUNRIN_HMAC_KEY must decode to at least 32 bytes.")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
