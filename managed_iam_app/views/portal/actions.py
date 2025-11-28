from __future__ import annotations

from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError
from django.core.exceptions import ValidationError as DjangoValidationError

from managed_iam.config import settings
from managed_iam.schemas.orgs import OrgRegisterResponse
from managed_iam.services.sts import STSService
from managed_iam_app.forms import (
    KeyPairForm,
    OrgRegisterForm,
    UserCreateForm,
    WorkloadDeleteForm,
    WorkloadDeployForm,
)
from managed_iam_app.views.portal.context import PortalContext
from managed_iam_app.views.portal.services import PortalServices


async def handle_create_user(form: UserCreateForm, *, services: PortalServices, context: PortalContext) -> UserCreateForm:
    if not form.is_valid():
        return form
    try:
        metadata = form.metadata_dict()
    except DjangoValidationError as exc:
        form.add_error("metadata", exc)
        return form

    record = await services.user.create_user(metadata=metadata)
    context.created_user_id = record.user_id
    context.add_alert("success", f"Created user_id {record.user_id}.")
    return form


async def handle_register_org(
    form: OrgRegisterForm,
    *,
    services: PortalServices,
    context: PortalContext,
) -> OrgRegisterForm:
    if not form.is_valid():
        return form

    user_id = form.cleaned_data["user_id"]
    org_name = form.cleaned_data["org_name"]
    exists = await services.user.ensure_user(user_id)
    if not exists:
        form.add_error("user_id", "User not found. Create it first.")
        return form

    try:
        result = await services.org.register_org(org_name=org_name, owner_user_id=user_id)
    except ValueError as exc:
        form.add_error("org_name", str(exc))
        return form

    context.registration_result = OrgRegisterResponse(
        org_name=result.org_name,
        api_key=result.api_key,
        external_id=result.external_id,
    )
    context.selected_org = result.org_name
    context.add_alert("success", f"Organisation {result.org_name} registered.")
    return form


async def handle_deploy_workload(
    form: WorkloadDeployForm,
    *,
    services: PortalServices,
    context: PortalContext,
) -> WorkloadDeployForm:
    if not form.is_valid():
        return form

    selected_org = form.cleaned_data["org_name"]
    user_id = form.cleaned_data["user_id"]
    api_key = form.cleaned_data["api_key"]
    parameters = {
        "EnvironmentName": form.cleaned_data["environment_name"],
        "BastionKeyPairName": form.cleaned_data["bastion_key_pair"],
        "BastionAllowedCidr": form.cleaned_data["bastion_allowed_cidr"],
        "DynamoTableName": form.cleaned_data["dynamo_table_name"],
    }
    desired = form.cleaned_data.get("asg_desired_capacity")
    if desired:
        parameters["AsgDesiredCapacity"] = desired

    record = await services.org.verify_api_key(org_name=selected_org, api_key=api_key)
    if not record or record.owner_user_id != user_id:
        form.add_error(None, "invalid organisation credentials")
        return form

    try:
        result = await services.workload.deploy_stack(
            org_name=selected_org,
            parameters=parameters,
        )
    except (ValueError, PermissionError, ClientError) as exc:
        form.add_error(None, str(exc))
        return form

    context.selected_org = selected_org
    context.workload_result = result
    context.add_alert("success", result.message)
    return form


async def handle_delete_workload(
    form: WorkloadDeleteForm,
    *,
    services: PortalServices,
    context: PortalContext,
) -> WorkloadDeleteForm:
    if not form.is_valid():
        return form

    selected_org = form.cleaned_data["org_name"]
    try:
        result = await services.workload.delete_stack(org_name=selected_org)
    except (ValueError, PermissionError, ClientError) as exc:
        form.add_error(None, str(exc))
        return form

    context.selected_org = selected_org
    context.workload_result = result
    context.add_alert("info", result.message)
    return form


async def handle_create_keypair(
    form: KeyPairForm,
    *,
    services: PortalServices,
    context: PortalContext,
) -> KeyPairForm:
    if not form.is_valid():
        return form

    user_id = form.cleaned_data["user_id"]
    org_name = form.cleaned_data["org_name"]
    api_key = form.cleaned_data["api_key"]
    key_name = form.cleaned_data["name"]
    record = await services.org.verify_api_key(org_name=org_name, api_key=api_key)
    if not record or record.owner_user_id != user_id:
        form.add_error(None, "invalid organisation credentials")
        return form
    if not record.validation_status or not record.account_id:
        form.add_error(None, "organisation must be validated before creating resources")
        return form

    sts_service = STSService(services.org)
    try:
        creds = await sts_service.issue_credentials(
            org_name=org_name,
            user_id=user_id,
            role_type="readonly",
            target_account_id=record.account_id,
            api_key=api_key,
        )
    except (ValueError, PermissionError, RuntimeError) as exc:
        form.add_error(None, str(exc))
        return form

    session = boto3.Session(
        aws_access_key_id=creds.access_key_id,
        aws_secret_access_key=creds.secret_access_key,
        aws_session_token=creds.session_token,
        region_name=settings.aws_region,
    )
    ec2 = session.client("ec2")
    try:
        response = ec2.create_key_pair(KeyName=key_name)
    except ClientError as exc:
        form.add_error(None, str(exc))
        return form

    key_material = response["KeyMaterial"]
    context.created_keypair_name = response["KeyName"]
    context.created_keypair_download = f"data:text/plain;charset=utf-8,{quote(key_material)}"
    context.add_alert(
        "success",
        f"Created key pair {key_name}. Download before navigating away.",
    )
    return form


__all__ = [
    "handle_create_keypair",
    "handle_create_user",
    "handle_delete_workload",
    "handle_deploy_workload",
    "handle_register_org",
]
