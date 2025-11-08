from __future__ import annotations

import json
import logging
from json import JSONDecodeError
import inspect
from typing import Any

import boto3
from botocore.exceptions import ClientError
from django.http import HttpRequest, JsonResponse, HttpResponseNotAllowed, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from pydantic import ValidationError

from managed_iam.schemas.integrate import IntegrationRequest, IntegrationResponse
from managed_iam.schemas.orgs import OrgRegisterRequest, OrgRegisterResponse
from managed_iam.schemas.sts import CredentialsRequest, CredentialsResponse
from managed_iam.schemas.users import UserCreateRequest, UserCreateResponse
from managed_iam.schemas.validate import ValidateRequest, ValidateResponse
from managed_iam.schemas.validation import ValidationWebhookResponse
from managed_iam.services import (
    IdempotencyError,
    IdempotencyService,
    RateLimitExceeded,
    RateLimiter,
)
from managed_iam.services.integration import IntegrationService
from managed_iam.services.orgs import OrganisationService
from managed_iam.services.sts import STSService
from managed_iam.services.users import UserService
from managed_iam.services.validation import ValidationWebhookService


logger = logging.getLogger("managed_iam.audit")
SWAGGER_UI_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Sigmoid Managed IAM API Docs</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
    <style>
      body {{ margin: 0; padding: 0; }}
    </style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.onload = function () {{
        window.ui = SwaggerUIBundle({{
          url: "{spec_url}",
          dom_id: "#swagger-ui",
          presets: [SwaggerUIBundle.presets.apis],
          layout: "BaseLayout",
        }});
      }};
    </script>
  </body>
</html>
"""


def _json_response(data: Any, *, status: int = 200) -> JsonResponse:
    return JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})


def _json_error(detail: Any, *, status: int) -> JsonResponse:
    payload = {"detail": detail}
    return _json_response(payload, status=status)


async def _read_body(request: HttpRequest) -> bytes:
    body = request.body
    if inspect.isawaitable(body):
        body = await body
    if isinstance(body, str):
        body = body.encode("utf-8")
    return body or b""


async def _parse_json_body(request: HttpRequest) -> Any:
    body = await _read_body(request)
    if not body:
        return {}
    try:
        return json.loads(body)
    except JSONDecodeError as exc:
        raise ValueError("invalid JSON body") from exc


@csrf_exempt
async def health(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    from managed_iam import get_version
    from managed_iam.config import settings

    return _json_response(
        {
            "status": "ok",
            "environment": settings.environment,
            "version": get_version(),
        }
    )


async def openapi_document(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    from managed_iam_app.openapi import build_openapi_schema

    base_url = request.build_absolute_uri("/")
    spec = build_openapi_schema(server_url=base_url.rstrip("/"))
    return _json_response(spec)


async def swagger_ui(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    spec_url = request.build_absolute_uri(reverse("openapi-json"))
    html = SWAGGER_UI_TEMPLATE.format(spec_url=spec_url)
    return HttpResponse(html, content_type="text/html")


@csrf_exempt
async def create_user(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        payload = await _parse_json_body(request)
        model = UserCreateRequest.model_validate(payload)
    except ValueError as exc:
        return _json_error(str(exc), status=400)
    except ValidationError as exc:
        return _json_error(exc.errors(), status=400)

    service = UserService()
    record = await service.create_user(metadata=model.metadata)
    response = UserCreateResponse(user_id=record.user_id, metadata=record.metadata)
    return _json_response(response.model_dump(), status=201)


@csrf_exempt
async def register_org(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user_id = request.GET.get("user_id")
    if not user_id:
        return _json_error("user_id query parameter required", status=400)

    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return _json_error("Idempotency-Key header required", status=400)

    try:
        payload = await _parse_json_body(request)
        model = OrgRegisterRequest.model_validate(payload)
    except ValueError as exc:
        return _json_error(str(exc), status=400)
    except ValidationError as exc:
        return _json_error(exc.errors(), status=400)

    user_service = UserService()
    if not await user_service.ensure_user(user_id):
        return _json_error("user not found", status=404)

    try:
        await IdempotencyService().claim(idempotency_key)
    except IdempotencyError as exc:
        return _json_error(str(exc), status=409)

    org_service = OrganisationService()
    try:
        result = await org_service.register_org(org_name=model.org_name, owner_user_id=user_id)
    except ValueError as exc:
        return _json_error(str(exc), status=409)

    logger.info(
        "org_registered",
        extra={
            "user_id": user_id,
            "org_name": result.org_name,
        },
    )

    response = OrgRegisterResponse(org_name=result.org_name, api_key=result.api_key, external_id=result.external_id)
    return _json_response(response.model_dump(), status=201)


@csrf_exempt
async def integrate(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user_id = request.GET.get("user_id")
    if not user_id:
        return _json_error("user_id query parameter required", status=400)

    try:
        payload = await _parse_json_body(request)
        model = IntegrationRequest.model_validate(payload)
    except ValueError as exc:
        return _json_error(str(exc), status=400)
    except ValidationError as exc:
        return _json_error(exc.errors(), status=400)

    user_service = UserService()
    if not await user_service.ensure_user(user_id):
        return _json_error("user not found", status=404)

    org_service = OrganisationService()
    record = await org_service.verify_api_key(org_name=model.org_name, api_key=model.api_key)
    if not record or record.owner_user_id != user_id:
        return _json_error("invalid credentials", status=401)

    links = await IntegrationService(org_service=org_service).build_links(
        org_name=model.org_name,
        aws_profile=model.aws_profile,
        expires_in=model.expires_in,
    )

    response = IntegrationResponse(**links.__dict__)
    return _json_response(response.model_dump())


@csrf_exempt
async def issue_credentials(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user_id = request.GET.get("user_id")
    if not user_id:
        return _json_error("user_id query parameter required", status=400)

    aws_profile = request.GET.get("aws_profile")

    try:
        payload = await _parse_json_body(request)
        model = CredentialsRequest.model_validate(payload)
    except ValueError as exc:
        return _json_error(str(exc), status=400)
    except ValidationError as exc:
        return _json_error(exc.errors(), status=400)

    limiter = RateLimiter()
    try:
        await limiter.check(f"credentials:{user_id}:{model.org_name}")
    except RateLimitExceeded as exc:
        return _json_error(str(exc), status=429)

    org_service = OrganisationService()
    integration_service = IntegrationService(org_service=org_service)

    user_service = UserService()
    if not await user_service.ensure_user(user_id):
        return _json_error("user not found", status=404)

    record = await org_service.verify_api_key(org_name=model.org_name, api_key=model.api_key)
    if not record or record.owner_user_id != user_id:
        return _json_error("invalid credentials", status=401)

    if not record.validation_status:
        links = await integration_service.build_links(org_name=model.org_name, aws_profile=aws_profile)
        return _json_error(
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
        return _json_error(str(exc), status=400)
    except PermissionError:
        links = await integration_service.build_links(org_name=model.org_name, aws_profile=aws_profile)
        return _json_error(
            {
                "message": "org validation incomplete",
                "console_url": links.console_url,
                "template_url": links.template_url,
                "aws_cli_command": links.aws_cli_command,
            },
            status=412,
        )
    except RuntimeError as exc:
        return _json_error(str(exc), status=502)

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
    return _json_response(response.model_dump())


@csrf_exempt
async def validate_credentials(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        payload = await _parse_json_body(request)
        model = ValidateRequest.model_validate(payload)
    except ValueError as exc:
        return _json_error(str(exc), status=400)
    except ValidationError as exc:
        return _json_error(exc.errors(), status=400)

    limiter = RateLimiter()
    try:
        await limiter.check(f"validate:{model.user_id}:{model.org_name}")
    except RateLimitExceeded as exc:
        return _json_error(str(exc), status=429)

    user_service = UserService()
    if not await user_service.ensure_user(model.user_id):
        return _json_error("user not found", status=404)

    org_service = OrganisationService()
    record = await org_service.verify_api_key(org_name=model.org_name, api_key=model.api_key)
    if not record or record.owner_user_id != model.user_id:
        return _json_error("invalid credentials", status=401)

    integration_service = IntegrationService(org_service=org_service)

    if not record.validation_status:
        links = await integration_service.build_links(
            org_name=model.org_name,
            aws_profile=model.aws_profile,
        )
        return _json_error(
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
        sts_client = session.client("sts")
        identity = sts_client.get_caller_identity()
        message = "credentials validated"
        logger.info(
            "sts_credentials_validated",
            extra={
                "user_id": model.user_id,
                "org_name": model.org_name,
                "identity_arn": identity.get("Arn"),
            },
        )
        response = ValidateResponse(success=True, identity_arn=identity.get("Arn"), message=message)
        return _json_response(response.model_dump())
    except ClientError as exc:
        return _json_error(str(exc), status=400)


@csrf_exempt
async def validation_webhook(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    headers = {key.lower(): value for key, value in request.headers.items()}
    body = await _read_body(request)
    service = ValidationWebhookService()
    try:
        result = await service.process_webhook(headers=headers, body=body)
    except ValueError as exc:
        return _json_error(str(exc), status=400)

    response = ValidationWebhookResponse(
        org_name=result.org_name,
        validated=result.validated,
        account_id=result.account_id,
        account_partition=result.account_partition,
        account_tags=result.account_tags,
    )
    return _json_response(response.model_dump())
