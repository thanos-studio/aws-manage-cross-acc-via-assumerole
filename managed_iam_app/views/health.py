from __future__ import annotations

from django.http import HttpRequest, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt

from managed_iam_app.views.utils import json_response


@csrf_exempt
async def health(request: HttpRequest):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    from managed_iam import get_version
    from managed_iam.config import settings

    payload = {
        "status": "ok",
        "environment": settings.environment,
        "version": get_version(),
    }
    return json_response(payload)


__all__ = ["health"]
