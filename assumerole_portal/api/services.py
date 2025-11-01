from __future__ import annotations

import secrets
from dataclasses import dataclass

from django.db import transaction

from .cloudformation import StackLaunchLink
from .crypto import CredentialCipher, sha256_digest
from .forms import StackRequest
from .models import Organization, PortalUser

API_KEY_LENGTH = 40
EXTERNAL_ID_LENGTH = 24


@dataclass(frozen=True)
class OrganizationCredentials:
    api_key: str
    external_id: str


class OrganizationService:
    def __init__(self, cipher: CredentialCipher):
        self._cipher = cipher

    def create_organization(self, *, owner: PortalUser, name: str, region: str) -> tuple[Organization, OrganizationCredentials]:
        api_key = secrets.token_urlsafe(API_KEY_LENGTH)[:API_KEY_LENGTH]
        external_id = secrets.token_urlsafe(EXTERNAL_ID_LENGTH)[:EXTERNAL_ID_LENGTH]
        api_cipher = self._cipher.encrypt(api_key)
        external_cipher = self._cipher.encrypt(external_id)
        with transaction.atomic():
            org = Organization.objects.create(
                name=name,
                owner=owner,
                aws_region=region,
                api_key_cipher=api_cipher,
                api_key_hash=sha256_digest(api_key),
                external_id_cipher=external_cipher,
            )
        return org, OrganizationCredentials(api_key=api_key, external_id=external_id)

    def build_stack_link(self, *, org: Organization, request: StackRequest) -> StackLaunchLink:
        parameters = {
            "OriginBucket": request.origin_bucket,
            "ViewerProtocolPolicy": "redirect-to-https",
            "ExternalId": org.name,
        }
        stack_name = f"{org.name}-cloudfront"
        return StackLaunchLink(region=request.region, stack_name=stack_name, parameters=parameters)

    def verify_user_access(self, *, user_id: str, org_name: str) -> Organization:
        try:
            owner = PortalUser.objects.get(public_id=user_id, is_active=True)
        except PortalUser.DoesNotExist as exc:
            raise PermissionError("Unknown or inactive user") from exc
        try:
            return Organization.objects.get(owner=owner, name=org_name)
        except Organization.DoesNotExist as exc:
            raise PermissionError("Organization not found for user") from exc
