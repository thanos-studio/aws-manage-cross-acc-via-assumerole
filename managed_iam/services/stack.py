"""Service for CloudFormation template access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import quote, quote_plus

import boto3

from managed_iam.config import settings


@dataclass
class StackTemplateInfo:
    template_url: str
    stack_name: str
    region: str


class StackService:
    def __init__(self, s3_client: boto3.client | None = None) -> None:
        self._bucket = settings.template_bucket
        self._template_key = settings.template_key
        self._s3 = None
        if not settings.template_public_access:
            self._s3 = s3_client or boto3.client("s3", region_name=settings.aws_region)

    def generate_template_url(self, *, org_name: str, expires_in: int = 3600) -> StackTemplateInfo:
        stack_name = f"Sigmoid-iam-{org_name}"
        if settings.template_public_access:
            url = self._public_template_url(self._template_key)
        else:
            url = self._presign(self._template_key, expires_in)
        return StackTemplateInfo(
            template_url=url,
            stack_name=stack_name,
            region=settings.aws_region,
        )

    def console_url(
        self,
        *,
        stack_name: str,
        template_url: str,
        region: str | None = None,
        parameters: Mapping[str, str] | None = None,
    ) -> str:
        region = region or settings.aws_region
        encoded_stack = quote(stack_name)
        encoded_template = quote(template_url, safe="")
        fragment = f"/stacks/create/review?stackName={encoded_stack}&templateURL={encoded_template}"
        if parameters:
            for key, value in parameters.items():
                fragment += f"&param_{quote_plus(key)}={quote_plus(value)}"
        return f"https://console.aws.amazon.com/cloudformation/home?region={quote_plus(region)}#{fragment}"

    def _public_template_url(self, key: str) -> str:
        key_path = quote(key)
        region_segment = f".{settings.aws_region}" if settings.aws_region != "us-east-1" else ""
        return f"https://{self._bucket}.s3{region_segment}.amazonaws.com/{key_path}"

    def _presign(self, key: str, expires_in: int) -> str:
        if self._s3 is None:
            raise RuntimeError("S3 client not initialized for presigned URL generation")
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
