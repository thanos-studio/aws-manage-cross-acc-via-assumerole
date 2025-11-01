from django.urls import path

from . import views


app_name = "api"

urlpatterns = [
    path("users", views.register_user, name="register_user"),
    path("register", views.register_organization, name="register_organization"),
    path("stack", views.stack_launch, name="stack_launch"),
    path("openapi.json", views.openapi_schema, name="schema"),
]
