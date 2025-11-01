from __future__ import annotations

from typing import Any


def build_schema(base_url: str) -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "AssumeRole Automation API",
            "version": "1.0.0",
            "description": "API endpoints for managing users, organizations, and CloudFormation launch URLs.",
        },
        "servers": [
            {"url": base_url.rstrip("/")},
        ],
        "paths": {
            "/api/users": {
                "post": {
                    "summary": "Create a new portal user",
                    "responses": {
                        "201": {
                            "description": "User created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UserResponse"}
                                }
                            },
                        }
                    },
                }
            },
            "/api/register": {
                "post": {
                    "summary": "Register an organization for a user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/OrganizationRequest"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Organization registered",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/OrganizationResponse"}
                                }
                            },
                        },
                        "403": {
                            "description": "User not allowed",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                            },
                        },
                        "409": {
                            "description": "Organization already exists",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                            },
                        },
                    },
                }
            },
            "/api/stack": {
                "get": {
                    "summary": "Generate a CloudFormation quick-create URL",
                    "parameters": [
                        {"name": "user_id", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "org_name", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "region", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "origin_bucket", "in": "query", "required": True, "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Launch URL details",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/StackResponse"}
                                }
                            },
                        },
                        "403": {
                            "description": "Forbidden",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                            },
                        },
                    },
                }
            },
        },
        "components": {
            "schemas": {
                "UserResponse": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string", "description": "Generated user identifier"}
                    },
                    "required": ["user_id"],
                },
                "OrganizationRequest": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "org_name": {"type": "string"},
                        "region": {"type": "string"},
                    },
                    "required": ["user_id", "org_name"],
                },
                "OrganizationResponse": {
                    "type": "object",
                    "properties": {
                        "org_name": {"type": "string"},
                        "region": {"type": "string"},
                        "api_key": {"type": "string"},
                        "external_id": {"type": "string"},
                        "validation_status": {"type": "string"},
                    },
                    "required": ["org_name", "region", "api_key", "external_id", "validation_status"],
                },
                "StackResponse": {
                    "type": "object",
                    "properties": {
                        "org_name": {"type": "string"},
                        "region": {"type": "string"},
                        "stack_name": {"type": "string"},
                        "launch_url": {"type": "string", "format": "uri"},
                        "parameters": {
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                    "required": ["org_name", "region", "stack_name", "launch_url", "parameters"],
                },
                "Error": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string"},
                    },
                    "required": ["error"],
                },
            }
        },
    }
