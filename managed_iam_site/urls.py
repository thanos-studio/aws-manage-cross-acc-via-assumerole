"""Root URL configuration for the Managed IAM Django project."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from managed_iam_app import views as managed_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("openapi.json", managed_views.openapi_document, name="openapi-json"),
    path("docs", managed_views.swagger_ui, name="swagger-ui"),
    path("docs/", managed_views.swagger_ui),
    path("", managed_views.portal, name="portal"),
    path("api/", include("managed_iam_app.urls")),
]
