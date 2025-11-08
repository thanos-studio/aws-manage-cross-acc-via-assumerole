"""Generate an OpenAPI/Swagger document for the Managed IAM API."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from managed_iam_app.openapi import build_openapi_schema


class Command(BaseCommand):
    help = "Render the OpenAPI specification to openapi.json (or a custom path)."

    def add_arguments(self, parser) -> None:  # pragma: no cover - Django wires parser.
        parser.add_argument(
            "--output",
            default="openapi.json",
            help="Target file path for the generated OpenAPI document.",
        )
        parser.add_argument(
            "--server-url",
            default=None,
            help="Optional base URL to embed in the OpenAPI servers list.",
        )

    def handle(self, *args, **options) -> None:
        spec = build_openapi_schema(server_url=options.get("server_url"))
        output_path = Path(options["output"]).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Swagger document written to {output_path}"))
