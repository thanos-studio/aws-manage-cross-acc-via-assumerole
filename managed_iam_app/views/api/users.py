from __future__ import annotations

from django.http import HttpRequest, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from pydantic import ValidationError

from managed_iam.schemas.users import UserCreateRequest, UserCreateResponse
from managed_iam.services.users import UserService
from managed_iam_app.views.utils import json_error, json_response, parse_json_body


@csrf_exempt
async def create_user(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        payload = await parse_json_body(request)
        model = UserCreateRequest.model_validate(payload)
    except ValueError as exc:
        return json_error(str(exc), status=400)
    except ValidationError as exc:
        return json_error(exc.errors(), status=400)

    record = await UserService().create_user(metadata=model.metadata)
    response = UserCreateResponse(user_id=record.user_id, metadata=record.metadata)
    return json_response(response.model_dump(), status=201)


__all__ = ["create_user"]
