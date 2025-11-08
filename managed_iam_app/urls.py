from __future__ import annotations

from django.urls import path

from . import views


app_name = "managed_iam_app"

urlpatterns = [
    path("health", views.health, name="health"),
    path("users", views.create_user, name="create_user"),
    path("register", views.register_org, name="register_org"),
    path("integrate", views.integrate, name="integrate"),
    path("credentials", views.issue_credentials, name="issue_credentials"),
    path("validate", views.validate_credentials, name="validate_credentials"),
    path("integrations/validate", views.validation_webhook, name="validation_webhook"),
]

