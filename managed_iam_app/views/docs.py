from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.urls import reverse

from managed_iam_app.openapi import build_openapi_schema
from managed_iam_app.views.utils import json_response


SWAGGER_UI_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Sunrin Managed IAM API Docs</title>
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


async def openapi_document(request: HttpRequest):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    base_url = request.build_absolute_uri("/")
    spec = build_openapi_schema(server_url=base_url.rstrip("/"))
    return json_response(spec)


async def swagger_ui(request: HttpRequest):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    spec_url = request.build_absolute_uri(reverse("openapi-json"))
    html = SWAGGER_UI_TEMPLATE.format(spec_url=spec_url)
    return HttpResponse(html, content_type="text/html")


__all__ = ["openapi_document", "swagger_ui"]
