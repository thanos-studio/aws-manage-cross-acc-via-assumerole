from __future__ import annotations

import logging

import boto3
from botocore.exceptions import ClientError
from django.http import HttpRequest, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from pydantic import ValidationError

from managed_iam.schemas.sts import CredentialsRequest, CredentialsResponse
from managed_iam.schemas.validate import ValidateRequest, ValidateResponse
from managed_iam.services import RateLimitExceeded, RateLimiter
from managed_iam.services.integration import IntegrationService
from managed_iam.services.orgs import OrganisationService
from managed_iam.services.sts import STSService
from managed_iam.services.users import UserService
from managed_iam_app.views.utils import json_error, json_response, parse_json_body


logger = logging.getLogger("managed_iam.audit")


@csrf_exempt
async def issue_credentials(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user_id = request.GET.get("user_id")
    if not user_id:
        return json_error("user_id query parameter required", status=400)

    aws_profile = request.GET.get("aws_profile")

    try:
        payload = await parse_json_body(request)
        model = CredentialsRequest.model_validate(payload)
    except ValueError as exc:
        return json_error(str(exc), status=400)
    except ValidationError as exc:
        return json_error(exc.errors(), status=400)

    limiter = RateLimiter()
    try:
        await limiter.check(f"credentials:{user_id}:{model.org_name}")
    except RateLimitExceeded as exc:
        return json_error(str(exc), status=429)

    user_service = UserService()
    if not await user_service.ensure_user(user_id):
        return json_error("user not found", status=404)

    org_service = OrganisationService()
    integration_service = IntegrationService(org_service=org_service)
    record = await org_service.verify_api_key(org_name=model.org_name, api_key=model.api_key)
    if not record or record.owner_user_id != user_id:
        return json_error("invalid credentials", status=401)

    if not record.validation_status:
        links = await integration_service.build_links(org_name=model.org_name, aws_profile=aws_profile)
        return json_error(
            {
                "message": "org validation incomplete",
                "console_url": links.console_url,
                "template_url": links.template_url,
                "aws_cli_command": links.aws_cli_command,
            },
            status=412,
        )

    sts_service = STSService(org_service)
    try:
        credentials = await sts_service.issue_credentials(
            org_name=model.org_name,
            user_id=user_id,
            role_type=model.role_type,
            target_account_id=model.target_account_id,
            api_key=model.api_key,
            aws_profile=aws_profile,
        )
    except ValueError as exc:
        return json_error(str(exc), status=400)
    except PermissionError:
        links = await integration_service.build_links(org_name=model.org_name, aws_profile=aws_profile)
        return json_error(
            {
                "message": "org validation incomplete",
                "console_url": links.console_url,
                "template_url": links.template_url,
                "aws_cli_command": links.aws_cli_command,
            },
            status=412,
        )
    except RuntimeError as exc:
        return json_error(str(exc), status=502)

    links = await integration_service.build_links(org_name=model.org_name, aws_profile=aws_profile)

    logger.info(
        "sts_credentials_issued",
        extra={
            "user_id": user_id,
            "org_name": model.org_name,
            "role_type": model.role_type,
            "target_account_id": model.target_account_id,
        },
    )

    response = CredentialsResponse(
        access_key_id=credentials.access_key_id,
        secret_access_key=credentials.secret_access_key,
        session_token=credentials.session_token,
        expiration=credentials.expiration,
        console_url=links.console_url,
        aws_cli_command=links.aws_cli_command,
        template_url=links.template_url,
        region=links.region,
    )
    return json_response(response.model_dump())


@csrf_exempt
async def validate_credentials(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        payload = await parse_json_body(request)
        model = ValidateRequest.model_validate(payload)
    except ValueError as exc:
        return json_error(str(exc), status=400)
    except ValidationError as exc:
        return json_error(exc.errors(), status=400)

    limiter = RateLimiter()
    try:
        await limiter.check(f"validate:{model.user_id}:{model.org_name}")
    except RateLimitExceeded as exc:
        return json_error(str(exc), status=429)

    user_service = UserService()
    if not await user_service.ensure_user(model.user_id):
        return json_error("user not found", status=404)

    org_service = OrganisationService()
    record = await org_service.verify_api_key(org_name=model.org_name, api_key=model.api_key)
    if not record or record.owner_user_id != model.user_id:
        return json_error("invalid credentials", status=401)

    integration_service = IntegrationService(org_service=org_service)
    if not record.validation_status:
        links = await integration_service.build_links(
            org_name=model.org_name,
            aws_profile=model.aws_profile,
        )
        return json_error(
            {
                "message": "org validation incomplete",
                "console_url": links.console_url,
                "template_url": links.template_url,
                "aws_cli_command": links.aws_cli_command,
            },
            status=412,
        )

    session = boto3.Session(
        aws_access_key_id=model.access_key_id,
        aws_secret_access_key=model.secret_access_key,
        aws_session_token=model.session_token,
        region_name=model.region,
    )

    try:
        identity = session.client("sts").get_caller_identity()
        logger.info(
            "sts_credentials_validated",
            extra={
                "user_id": model.user_id,
                "org_name": model.org_name,
                "identity_arn": identity.get("Arn"),
            },
        )
        response = ValidateResponse(success=True, identity_arn=identity.get("Arn"), message="credentials validated")
        return json_response(response.model_dump())
    except ClientError as exc:
        return json_error(str(exc), status=400)


__all__ = ["issue_credentials", "validate_credentials"]
