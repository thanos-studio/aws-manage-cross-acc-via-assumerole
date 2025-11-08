"""Module entrypoint for running the Django development server."""

from __future__ import annotations

import os

from django.core.management import execute_from_command_line


def main() -> None:  # pragma: no cover - CLI entry
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "managed_iam_site.settings")
    execute_from_command_line(["manage.py", "runserver", "0.0.0.0:8000"])


if __name__ == "__main__":  # pragma: no cover
    main()
