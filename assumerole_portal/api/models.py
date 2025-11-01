from __future__ import annotations

import secrets
from django.db import models


class PortalUser(models.Model):
    """Represents an operator that can manage organizations."""

    public_id = models.CharField(max_length=32, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):  # type: ignore[override]
        if not self.public_id:
            self.public_id = secrets.token_hex(16)
        super().save(*args, **kwargs)

    def __str__(self) -> str:  # pragma: no cover
        return self.public_id


class Organization(models.Model):
    """Stores org credentials and state for AssumeRole flows."""

    PENDING = "pending"
    VALIDATED = "validated"

    VALIDATION_CHOICES = [
        (PENDING, "Pending"),
        (VALIDATED, "Validated"),
    ]

    name = models.CharField(max_length=64, unique=True)
    owner = models.ForeignKey(PortalUser, related_name="organizations", on_delete=models.CASCADE)
    aws_region = models.CharField(max_length=32, default="us-east-1")
    api_key_cipher = models.TextField()
    api_key_hash = models.CharField(max_length=64)
    external_id_cipher = models.TextField()
    validation_status = models.CharField(max_length=16, choices=VALIDATION_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.name} ({self.owner.public_id})"
