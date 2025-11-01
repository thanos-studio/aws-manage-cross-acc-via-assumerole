from __future__ import annotations

import json
from http import HTTPStatus

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .crypto import CredentialCipher, EncryptionError
from .forms import OrganizationRegistrationForm, StackLaunchForm, UserRegistrationForm
from .models import Organization, PortalUser
from .schema import build_schema
from .services import OrganizationService


def _service() -> OrganizationService:
    cipher = CredentialCipher.from_env()
    return OrganizationService(cipher)


def _json_error(message: str, status: int = HTTPStatus.BAD_REQUEST) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


@csrf_exempt
def register_user(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return _json_error("Method not allowed", HTTPStatus.METHOD_NOT_ALLOWED)

    form = UserRegistrationForm(json.loads(request.body or b"{}"))
    if not form.is_valid():
        return _json_error(form.errors.as_json())

    user = PortalUser.objects.create()
    return JsonResponse({"user_id": user.public_id}, status=HTTPStatus.CREATED)


@csrf_exempt
def register_organization(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return _json_error("Method not allowed", HTTPStatus.METHOD_NOT_ALLOWED)

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _json_error("Invalid JSON payload")

    form = OrganizationRegistrationForm(payload)
    if not form.is_valid():
        return _json_error(form.errors.as_json())

    service = _service()
    try:
        owner = PortalUser.objects.get(public_id=form.cleaned_data["user_id"], is_active=True)
    except PortalUser.DoesNotExist:
        return _json_error("Unknown or inactive user", HTTPStatus.FORBIDDEN)

    if Organization.objects.filter(name=form.cleaned_data["org_name"]).exists():
        return _json_error("Organization already registered", HTTPStatus.CONFLICT)

    try:
        org, creds = service.create_organization(
            owner=owner,
            name=form.cleaned_data["org_name"],
            region=form.cleaned_data["region"],
        )
    except EncryptionError as exc:
        return _json_error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    return JsonResponse(
        {
            "org_name": org.name,
            "region": org.aws_region,
            "api_key": creds.api_key,
            "external_id": creds.external_id,
            "validation_status": org.validation_status,
        },
        status=HTTPStatus.CREATED,
    )


def stack_launch(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return _json_error("Method not allowed", HTTPStatus.METHOD_NOT_ALLOWED)

    form = StackLaunchForm(request.GET)
    if not form.is_valid():
        return _json_error(form.errors.as_json())

    service = _service()
    try:
        org = service.verify_user_access(
            user_id=form.cleaned_data["user_id"],
            org_name=form.cleaned_data["org_name"],
        )
    except PermissionError as exc:
        return _json_error(str(exc), HTTPStatus.FORBIDDEN)
    except EncryptionError as exc:
        return _json_error(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    stack_request = form.to_stack_request()
    launch_link = service.build_stack_link(org=org, request=stack_request)

    return JsonResponse(
        {
            "org_name": org.name,
            "region": stack_request.region,
            "stack_name": launch_link.stack_name,
            "launch_url": launch_link.console_url(),
            "parameters": launch_link.parameters,
        }
    )


def openapi_schema(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return _json_error("Method not allowed", HTTPStatus.METHOD_NOT_ALLOWED)

    base_url = request.build_absolute_uri("/")
    schema = build_schema(base_url)
    return JsonResponse(schema, json_dumps_params={"indent": 2})
