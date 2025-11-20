"""CloudFormation deployment helpers for the workload stack."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from managed_iam.config import settings
from managed_iam.repos import OrgRecord
from managed_iam.services.orgs import OrganisationService


WORKLOAD_TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "cloudformation" / "workload-stack.yaml"


@dataclass
class WorkloadStatus:
    stack_name: str
    stack_id: str | None
    status: str | None
    outputs: dict[str, str]
    last_updated: str | None


@dataclass
class WorkloadActionResult:
    action: str
    message: str
    stack_id: str | None = None


class WorkloadStackService:
    """Assume the customer role and manage the workload CloudFormation stack."""

    def __init__(
        self,
        *,
        template_path: Path | None = None,
        org_service: OrganisationService | None = None,
    ) -> None:
        self._template_path = template_path or WORKLOAD_TEMPLATE_PATH
        self._template_body = self._template_path.read_text(encoding="utf-8")
        self._org_service = org_service or OrganisationService()

    def _stack_name(self, org_name: str) -> str:
        return f"Sunrin-Workload-{org_name}"

    async def _require_validated_org(self, org_name: str) -> OrgRecord:
        record = await self._org_service.get_org(org_name)
        if not record:
            raise ValueError("organisation not found")
        if not record.validation_status or not record.account_id:
            raise PermissionError("organisation is not validated yet")
        return record

    async def describe_stack(self, org_name: str) -> WorkloadStatus | None:
        record = await self._require_validated_org(org_name)
        return await self._run_in_thread(self._describe_stack_sync, record)

    async def deploy_stack(self, org_name: str, parameters: dict[str, Any]) -> WorkloadActionResult:
        record = await self._require_validated_org(org_name)
        return await self._run_in_thread(self._deploy_stack_sync, record, parameters)

    async def delete_stack(self, org_name: str) -> WorkloadActionResult:
        record = await self._require_validated_org(org_name)
        return await self._run_in_thread(self._delete_stack_sync, record)

    async def _run_in_thread(self, func, *args, **kwargs):
        import asyncio

        return await asyncio.to_thread(func, *args, **kwargs)

    def _assume_role(self, record: OrgRecord) -> dict[str, Any]:
        external_id = self._org_service.decrypt_external_id(record)
        session_base = settings.session_name_format.format(org_name=record.org_name, user_id=record.owner_user_id)
        timestamp_suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        available = 64 - (len(timestamp_suffix) + 1)
        if available < 1:
            available = 1
        session_name = f"{session_base[:available]}-{timestamp_suffix}"
        role_arn = f"arn:aws:iam::{record.account_id}:role/{settings.provider_readonly_role}"
        sts_client = boto3.client("sts", region_name=settings.aws_region)
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            ExternalId=external_id,
            DurationSeconds=3600,
        )
        return response["Credentials"]

    def _cfn_client(self, creds: dict[str, Any]):
        return boto3.client(
            "cloudformation",
            region_name=settings.aws_region,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )

    def _describe_stack_sync(self, record: OrgRecord) -> WorkloadStatus | None:
        creds = self._assume_role(record)
        client = self._cfn_client(creds)
        stack_name = self._stack_name(record.org_name)
        try:
            response = client.describe_stacks(StackName=stack_name)
        except ClientError as exc:
            message = exc.response.get("Error", {}).get("Message", "")
            if "does not exist" in message or "not exist" in message:
                return None
            raise

        stack = response["Stacks"][0]
        outputs = {item["OutputKey"]: item["OutputValue"] for item in stack.get("Outputs", [])}
        return WorkloadStatus(
            stack_name=stack["StackName"],
            stack_id=stack.get("StackId"),
            status=stack.get("StackStatus"),
            outputs=outputs,
            last_updated=stack.get("LastUpdatedTime", stack.get("CreationTime")).isoformat()
            if hasattr(stack.get("LastUpdatedTime"), "isoformat")
            else None,
        )

    def _deploy_stack_sync(self, record: OrgRecord, parameters: dict[str, Any]) -> WorkloadActionResult:
        creds = self._assume_role(record)
        client = self._cfn_client(creds)
        stack_name = self._stack_name(record.org_name)
        exists = self._stack_exists(client, stack_name)
        param_list = [
            {"ParameterKey": key, "ParameterValue": str(value)}
            for key, value in parameters.items()
            if value not in (None, "")
        ]
        capabilities = ["CAPABILITY_NAMED_IAM", "CAPABILITY_IAM"]

        if not exists:
            response = client.create_stack(
                StackName=stack_name,
                TemplateBody=self._template_body,
                Parameters=param_list,
                Capabilities=capabilities,
            )
            return WorkloadActionResult(
                action="create",
                stack_id=response.get("StackId"),
                message="Workload stack creation started.",
            )

        try:
            response = client.update_stack(
                StackName=stack_name,
                TemplateBody=self._template_body,
                Parameters=param_list,
                Capabilities=capabilities,
            )
        except ClientError as exc:
            message = exc.response.get("Error", {}).get("Message", "")
            if "No updates are to be performed" in message:
                return WorkloadActionResult(action="noop", stack_id=None, message="No changes detected.")
            raise

        return WorkloadActionResult(
            action="update",
            stack_id=response.get("StackId"),
            message="Workload stack update started.",
        )

    def _delete_stack_sync(self, record: OrgRecord) -> WorkloadActionResult:
        creds = self._assume_role(record)
        client = self._cfn_client(creds)
        stack_name = self._stack_name(record.org_name)
        exists = self._stack_exists(client, stack_name)
        if not exists:
            return WorkloadActionResult(action="noop", stack_id=None, message="Stack not found.")

        client.delete_stack(StackName=stack_name)
        return WorkloadActionResult(
            action="delete",
            stack_id=stack_name,
            message="Workload stack deletion started.",
        )

    @staticmethod
    def _stack_exists(client, stack_name: str) -> bool:
        try:
            client.describe_stacks(StackName=stack_name)
            return True
        except ClientError as exc:
            message = exc.response.get("Error", {}).get("Message", "")
            if "does not exist" in message or "not exist" in message:
                return False
            raise
