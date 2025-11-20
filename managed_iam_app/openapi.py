"""Build an OpenAPI/Swagger document for the Managed IAM API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from managed_iam import get_version
from managed_iam.schemas.integrate import IntegrationRequest, IntegrationResponse
from managed_iam.schemas.orgs import OrgRegisterRequest, OrgRegisterResponse
from managed_iam.schemas.sts import CredentialsRequest, CredentialsResponse
from managed_iam.schemas.users import UserCreateRequest, UserCreateResponse
from managed_iam.schemas.validate import ValidateRequest, ValidateResponse
from managed_iam.schemas.validation import ValidationWebhookPayload, ValidationWebhookResponse

Schema = Dict[str, Any]


def _model_schema(model: type) -> Schema:
    return model.model_json_schema(ref_template="#/components/schemas/{model}")


def _json_ref(schema_name: str) -> Schema:
    return {"$ref": f"#/components/schemas/{schema_name}"}


def _json_response(schema_name: str, *, example: Dict[str, Any] | None = None) -> Dict[str, Any]:
    content: Dict[str, Any] = {
        "schema": _json_ref(schema_name),
    }
    if example is not None:
        content["example"] = example
    return {
        "application/json": content,
    }


def _error_response(description: str) -> Dict[str, Any]:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": _json_ref("ErrorResponse"),
            }
        },
    }


def build_openapi_schema(*, server_url: Optional[str] = None) -> Dict[str, Any]:
    """Return an OpenAPI 3.0 specification for the external API surface."""
    component_models: dict[str, type] = {
        "UserCreateRequest": UserCreateRequest,
        "UserCreateResponse": UserCreateResponse,
        "OrgRegisterRequest": OrgRegisterRequest,
        "OrgRegisterResponse": OrgRegisterResponse,
        "IntegrationRequest": IntegrationRequest,
        "IntegrationResponse": IntegrationResponse,
        "CredentialsRequest": CredentialsRequest,
        "CredentialsResponse": CredentialsResponse,
        "ValidateRequest": ValidateRequest,
        "ValidateResponse": ValidateResponse,
        "ValidationWebhookPayload": ValidationWebhookPayload,
        "ValidationWebhookResponse": ValidationWebhookResponse,
    }

    components = {
        "schemas": {name: _model_schema(model) for name, model in component_models.items()},
    }
    components["schemas"]["ErrorResponse"] = {
        "type": "object",
        "required": ["detail"],
        "properties": {
            "detail": {
                "description": "Human readable error message or structured validation errors.",
            }
        },
    }
    components["schemas"]["HealthResponse"] = {
        "type": "object",
        "required": ["status", "environment", "version"],
        "properties": {
            "status": {"type": "string", "example": "ok"},
            "environment": {"type": "string", "example": "dev"},
            "version": {"type": "string", "example": "0.1.0"},
        },
    }

    def _health_response(description: str) -> Dict[str, Any]:
        return {
            "200": {
                "description": description,
                "content": {
                    "application/json": {
                        "schema": _json_ref("HealthResponse"),
                    }
                },
            }
        }

    def _success_response(schema_name: str, description: str, status: str = "200") -> Dict[str, Any]:
        return {
            status: {
                "description": description,
                "content": _json_response(schema_name),
            }
        }

    error_common = {
        "400": _error_response("Invalid input payload."),
    }
    user_id_param = {
        "name": "user_id",
        "in": "query",
        "required": True,
        "schema": {"type": "string"},
        "description": "Operator identifier issued via POST /api/users.",
    }
    idempotency_header = {
        "name": "Idempotency-Key",
        "in": "header",
        "required": True,
        "schema": {"type": "string"},
        "description": "Opaque identifier that prevents duplicate organisation registrations.",
    }

    paths: Dict[str, Any] = {
        "/api/health": {
            "get": {
                "operationId": "healthProbe",
                "summary": "Health check endpoint",
                "tags": ["Health"],
                "responses": _health_response("Service is reachable."),
            }
        },
        "/api/users": {
            "post": {
                "operationId": "createUser",
                "summary": "Issue a user identifier for Sunrin operators.",
                "tags": ["Users"],
                "requestBody": {
                    "required": False,
                    "content": _json_response(
                        "UserCreateRequest",
                        example={
                            "metadata": {
                                "team": "sunrin-platform",
                                "region": "us-east-1",
                            }
                        },
                    ),
                },
                "responses": {
                    **_success_response("UserCreateResponse", "User created.", status="201"),
                    **error_common,
                },
            }
        },
        "/api/register": {
            "post": {
                "operationId": "registerOrg",
                "summary": "Register an organisation and issue API credentials.",
                "tags": ["Organisations"],
                "parameters": [
                    user_id_param,
                    idempotency_header,
                ],
                "requestBody": {
                    "required": True,
                    "content": _json_response("OrgRegisterRequest"),
                },
                "responses": {
                    **_success_response("OrgRegisterResponse", "Organisation registered.", status="201"),
                    "404": _error_response("User not found."),
                    "409": _error_response("Organisation already exists or idempotency conflict."),
                    **error_common,
                },
            }
        },
        "/api/integrate": {
            "post": {
                "operationId": "integrateOrg",
                "summary": "Generate console links and CLI commands for onboarding.",
                "tags": ["Integrations"],
                "parameters": [
                    user_id_param,
                ],
                "requestBody": {
                    "required": True,
                    "content": _json_response("IntegrationRequest"),
                },
                "responses": {
                    **_success_response("IntegrationResponse", "Integration links issued."),
                    "401": _error_response("API key mismatch."),
                    "404": _error_response("User not found."),
                    **error_common,
                },
            }
        },
        "/api/credentials": {
            "post": {
                "operationId": "issueCredentials",
                "summary": "Assume roles in the managed account once validation completes.",
                "tags": ["Credentials"],
                "parameters": [
                    user_id_param,
                    {
                        "name": "aws_profile",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Optional AWS profile label echoed back in responses.",
                    },
                ],
                "requestBody": {
                    "required": True,
                    "content": _json_response("CredentialsRequest"),
                },
                "responses": {
                    **_success_response("CredentialsResponse", "STS credentials issued."),
                    "401": _error_response("API key mismatch."),
                    "404": _error_response("User not found."),
                    "412": _error_response("Organisation validation incomplete."),
                    "429": _error_response("Rate limit exceeded."),
                    "502": _error_response("Upstream AWS error during assume_role."),
                    **error_common,
                },
            }
        },
        "/api/validate": {
            "post": {
                "operationId": "validateCredentials",
                "summary": "Verify arbitrary STS credentials against the Managed IAM policy.",
                "tags": ["Credentials"],
                "requestBody": {
                    "required": True,
                    "content": _json_response("ValidateRequest"),
                },
                "responses": {
                    **_success_response("ValidateResponse", "Credentials validated."),
                    "401": _error_response("API key mismatch."),
                    "404": _error_response("User not found."),
                    "412": _error_response("Organisation validation incomplete."),
                    "429": _error_response("Rate limit exceeded."),
                    **error_common,
                },
            }
        },
        "/api/integrations/validate": {
            "post": {
                "operationId": "validationWebhook",
                "summary": "Webhook consumed by the validation Lambda stack.",
                "tags": ["Integrations"],
                "requestBody": {
                    "required": True,
                    "content": _json_response("ValidationWebhookPayload"),
                },
                "responses": {
                    **_success_response(
                        "ValidationWebhookResponse",
                        "Validation result recorded.",
                    ),
                    **error_common,
                },
            }
        },
    }

    effective_server = server_url or "http://localhost:8000"

    spec: Dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": "Sunrin Managed IAM API",
            "version": get_version(),
            "description": "Programmatic interface for provisioning and validating Sunrin managed IAM roles.",
        },
        "servers": [
            {"url": effective_server, "description": "API base URL"},
        ],
        "paths": paths,
        "components": components,
        "tags": [
            {"name": "Health"},
            {"name": "Users"},
            {"name": "Organisations"},
            {"name": "Integrations"},
            {"name": "Credentials"},
        ],
    }
    return spec


__all__ = ["build_openapi_schema"]
