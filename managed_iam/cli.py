"""CLI helpers exposed via Poetry scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

from django.core.management import execute_from_command_line


def _configure_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "managed_iam_site.settings")


def _manage_py() -> Path:
    return Path(__file__).resolve().parents[1] / "manage.py"


def _run_command(argv: Iterable[str]) -> None:
    args = list(argv)
    args[0] = str(_manage_py())
    sys.argv = args
    execute_from_command_line(args)


def run_dev_server() -> None:
    """Run Django's autoreloading development server."""
    _configure_django()
    host = os.environ.get("SUNRIN_DEV_HOST", "0.0.0.0")
    port = os.environ.get("SUNRIN_DEV_PORT", "8000")
    _run_command(["manage.py", "runserver", f"{host}:{port}"])


def run_prod_server() -> None:
    """Launch gunicorn for production-style serving."""
    _configure_django()
    from gunicorn.app.wsgiapp import WSGIApplication

    bind = os.environ.get("SUNRIN_GUNICORN_BIND", "0.0.0.0:8000")
    workers = os.environ.get("SUNRIN_GUNICORN_WORKERS", "4")

    sys.argv = [
        "gunicorn",
        "managed_iam_site.wsgi:application",
        "--bind",
        bind,
        "--workers",
        workers,
    ]
    WSGIApplication().run()


__all__ = ["run_dev_server", "run_prod_server"]
