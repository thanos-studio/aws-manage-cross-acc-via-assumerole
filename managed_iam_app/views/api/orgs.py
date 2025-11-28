from __future__ import annotations

import logging

from django.http import HttpRequest, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from pydantic import ValidationError

from managed_iam.schemas.integrate import IntegrationRequest, IntegrationResponse
from managed_iam.schemas.orgs import OrgRegisterRequest, OrgRegisterResponse
from managed_iam.services import IdempotencyError, IdempotencyService
from managed_iam.services.integration import IntegrationService
from managed_iam.services.orgs import OrganisationService
from managed_iam.services.users import UserService
from managed_iam_app.views.utils import json_error, json_response, parse_json_body


logger = logging.getLogger("managed_iam.audit")


@csrf_exempt
async def register_org(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user_id = request.GET.get("user_id")
    if not user_id:
        return json_error("user_id query parameter required", status=400)

    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return json_error("Idempotency-Key header required", status=400)

    try:
        payload = await parse_json_body(request)
        model = OrgRegisterRequest.model_validate(payload)
    except ValueError as exc:
        return json_error(str(exc), status=400)
    except ValidationError as exc:
        return json_error(exc.errors(), status=400)

    user_service = UserService()
    if not await user_service.ensure_user(user_id):
        return json_error("user not found", status=404)

    try:
        await IdempotencyService().claim(idempotency_key)
    except IdempotencyError as exc:
        return json_error(str(exc), status=409)

    org_service = OrganisationService()
    try:
        result = await org_service.register_org(org_name=model.org_name, owner_user_id=user_id)
    except ValueError as exc:
        return json_error(str(exc), status=409)

    logger.info(
        "org_registered",
        extra={
            "user_id": user_id,
            "org_name": result.org_name,
        },
    )

    response = OrgRegisterResponse(org_name=result.org_name, api_key=result.api_key, external_id=result.external_id)
    return json_response(response.model_dump(), status=201)


@csrf_exempt
async def integrate(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user_id = request.GET.get("user_id")
    if not user_id:
        return json_error("user_id query parameter required", status=400)

    try:
        payload = await parse_json_body(request)
        model = IntegrationRequest.model_validate(payload)
    except ValueError as exc:
        return json_error(str(exc), status=400)
    except ValidationError as exc:
        return json_error(exc.errors(), status=400)

    user_service = UserService()
    if not await user_service.ensure_user(user_id):
        return json_error("user not found", status=404)

    org_service = OrganisationService()
    record = await org_service.verify_api_key(org_name=model.org_name, api_key=model.api_key)
    if not record or record.owner_user_id != user_id:
        return json_error("invalid credentials", status=401)

    links = await IntegrationService(org_service=org_service).build_links(
        org_name=model.org_name,
        aws_profile=model.aws_profile,
        expires_in=model.expires_in,
    )

    response = IntegrationResponse(**links.__dict__)
    return json_response(response.model_dump())


__all__ = ["register_org", "integrate"]
