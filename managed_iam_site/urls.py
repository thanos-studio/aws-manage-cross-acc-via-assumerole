"""Root URL configuration for the Managed IAM Django project."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("managed_iam_app.urls")),
]

