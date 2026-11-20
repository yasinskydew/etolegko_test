"""Shared OpenAPI metadata for FastAPI app and routers."""

from typing import Any

from app.schemas.errors import ErrorBody

OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "health",
        "description": "Liveness probe. No authentication.",
    },
    {
        "name": "auth",
        "description": "JWT login. Issue a bearer token for protected routes.",
    },
    {
        "name": "companies",
        "description": (
            "Company lifecycle and stream editor API. "
            "Offer edits are drafted on FE; Push uses PUT /companies/{id}. "
            "Keitaro is reached only from the backend."
        ),
    },
    {
        "name": "offers",
        "description": "Read-only offer catalog proxied from Keitaro (or local noop mock).",
    },
]

APP_DESCRIPTION = """
Adrobot / Keitaro wrapper admin API.

**Auth:** `Authorization: Bearer <jwt>` on all routes except `POST /auth/login` and `GET /health`.

**Errors:** JSON body `{ "error": "<code>", "message": "<text>", "fields"?: {...} }`.

**Drafts:** offer/geo edits live in FE localStorage; Push applies via `PUT /companies/{id}`.

Canonical behaviour: `docs/api_contracts.md` and `task/system-design.md`.
""".strip()

ERROR_401: dict[str, Any] = {
    "model": ErrorBody,
    "description": "Missing or invalid JWT (`unauthorized`).",
}
ERROR_404: dict[str, Any] = {
    "model": ErrorBody,
    "description": "Company or stream not found (`not_found`).",
}
ERROR_409: dict[str, Any] = {
    "model": ErrorBody,
    "description": (
        "Conflict: `name_taken`, `idempotency_conflict`, or `campaign_missing`."
    ),
}
ERROR_422: dict[str, Any] = {
    "model": ErrorBody,
    "description": "Validation failed (`validation_error` or `unknown_geo`).",
}
ERROR_502: dict[str, Any] = {
    "model": ErrorBody,
    "description": "Keitaro upstream error (`keitaro_bad_gateway`).",
}
ERROR_504: dict[str, Any] = {
    "model": ErrorBody,
    "description": "Keitaro timeout (`keitaro_timeout`).",
}

RESP_AUTH = {
    401: ERROR_401,
}
RESP_PROTECTED = {
    401: ERROR_401,
    502: ERROR_502,
    504: ERROR_504,
}
RESP_COMPANY = {
    **RESP_PROTECTED,
    404: ERROR_404,
    409: ERROR_409,
    422: ERROR_422,
}
