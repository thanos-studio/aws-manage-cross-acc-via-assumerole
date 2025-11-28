from __future__ import annotations

import inspect
import json
from typing import Any

from django.http import HttpRequest, JsonResponse


def json_response(data: Any, *, status: int = 200) -> JsonResponse:
    """Return a JSON response with UTF-8 safe dumps settings."""
    return JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})


def json_error(detail: Any, *, status: int) -> JsonResponse:
    """Return a consistent error payload."""
    return json_response({"detail": detail}, status=status)


async def read_body(request: HttpRequest) -> bytes:
    """Read and normalise the request body into bytes."""
    body = request.body
    if inspect.isawaitable(body):
        body = await body
    if isinstance(body, str):
        body = body.encode("utf-8")
    return body or b""


async def parse_json_body(request: HttpRequest) -> Any:
    """Parse the incoming body as JSON, returning {} for empty bodies."""
    body = await read_body(request)
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON body") from exc


__all__ = ["json_response", "json_error", "read_body", "parse_json_body"]
