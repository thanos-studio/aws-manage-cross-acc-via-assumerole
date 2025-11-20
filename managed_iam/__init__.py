"""Managed IAM prototype package."""

from importlib import metadata


def get_version() -> str:
    """Return package version, defaulting to dev if unavailable."""
    try:
        return metadata.version("sunrin-aws-managed-iam-django")
    except metadata.PackageNotFoundError:  # pragma: no cover - during tests
        return "0.0.0-dev"


__all__ = ["get_version"]
