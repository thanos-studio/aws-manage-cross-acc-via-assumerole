from __future__ import annotations

from django.http import HttpRequest, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt

from managed_iam.schemas.validation import ValidationWebhookResponse
from managed_iam.services.validation import ValidationWebhookService
from managed_iam_app.views.utils import json_error, json_response, read_body


@csrf_exempt
async def validation_webhook(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    headers = {key.lower(): value for key, value in request.headers.items()}
    body = await read_body(request)
    service = ValidationWebhookService()
    try:
        result = await service.process_webhook(headers=headers, body=body)
    except ValueError as exc:
        return json_error(str(exc), status=400)

    response = ValidationWebhookResponse(
        org_name=result.org_name,
        validated=result.validated,
        account_id=result.account_id,
        account_partition=result.account_partition,
        account_tags=result.account_tags,
    )
    return json_response(response.model_dump())


__all__ = ["validation_webhook"]
