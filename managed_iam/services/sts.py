"""Service for STS credential issuance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, ProfileNotFound

from managed_iam.config import settings
from managed_iam.repos import OrgRecord
from managed_iam.services.orgs import OrganisationService


@dataclass
class TemporaryCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str


ROLE_MAP = {
    "readonly": settings.provider_readonly_role,
}


class STSService:
    def __init__(self, org_service: OrganisationService | None = None) -> None:
        self._org_service = org_service or OrganisationService()

    def _build_client(self, aws_profile: str | None = None):
        if aws_profile:
            try:
                session = boto3.session.Session(profile_name=aws_profile)
            except ProfileNotFound as exc:
                raise ValueError(f"aws profile '{aws_profile}' not found") from exc
            return session.client("sts", region_name=settings.aws_region)
        return boto3.client("sts", region_name=settings.aws_region)

    async def issue_credentials(
        self,
        *,
        org_name: str,
        user_id: str,
        role_type: str,
        target_account_id: str,
        api_key: str,
        aws_profile: str | None = None,
    ) -> TemporaryCredentials:
        record = await self._org_service.verify_api_key(org_name=org_name, api_key=api_key)
        if not record:
            raise ValueError("invalid api key")
        if not record.validation_status:
            raise PermissionError("org not validated")

        role_name = ROLE_MAP.get(role_type.lower())
        if not role_name:
            raise ValueError("invalid role type")

        external_id = self._org_service.decrypt_external_id(record)
        session_base = settings.session_name_format.format(org_name=org_name, user_id=user_id)
        timestamp_suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        available = 64 - (len(timestamp_suffix) + 1)
        if available < 1:
            available = 1
        session_name = f"{session_base[:available]}-{timestamp_suffix}"
        role_arn = f"arn:aws:iam::{target_account_id}:role/{role_name}"
        sts_client = self._build_client(aws_profile)

        try:
            response = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name,
                ExternalId=external_id,
                DurationSeconds=3600,
            )
        except ClientError as exc:  # pragma: no cover - boto3 handles error codes
            raise RuntimeError("sts assume role failed") from exc

        creds = response["Credentials"]
        return TemporaryCredentials(
            access_key_id=creds["AccessKeyId"],
            secret_access_key=creds["SecretAccessKey"],
            session_token=creds["SessionToken"],
            expiration=creds["Expiration"].isoformat() if hasattr(creds["Expiration"], "isoformat") else str(creds["Expiration"]),
        )
