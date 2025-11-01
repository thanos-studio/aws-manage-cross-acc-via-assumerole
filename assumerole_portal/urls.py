"""Root URL configuration for assumerole_portal."""
from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView, TemplateView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="api-docs", permanent=False)),
    path("api/", include(("assumerole_portal.api.urls", "api"), namespace="api")),
    path(
        "docs",
        TemplateView.as_view(
            template_name="docs/swagger.html",
            extra_context={"schema_url": reverse_lazy("api:schema")},
        ),
        name="api-docs",
    ),
]
