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

**Errors:** every non-2xx response is `ErrorBody`
`{ "error": "<code>", "message": "<text>", "fields"?: {"<field>": "<text>"} }`,
including request validation (`422 validation_error` with `fields`). Each `error` code
has one HTTP status; see the `ErrorBody` schema.

**Drafts:** offer/geo edits live in FE localStorage; Push applies via `PUT /companies/{id}`.
""".strip()

ERROR_401: dict[str, Any] = {
    "model": ErrorBody,
    "description": "`unauthorized`: missing or invalid JWT / credentials.",
}
ERROR_404: dict[str, Any] = {
    "model": ErrorBody,
    "description": "`not_found`: company or stream does not exist.",
}
ERROR_409: dict[str, Any] = {
    "model": ErrorBody,
    "description": (
        "`name_taken`, `idempotency_conflict`, `company_not_ready` (creating / failed), "
        "`campaign_missing`, `concurrent_update`, `keitaro_not_found`."
    ),
}
ERROR_422: dict[str, Any] = {
    "model": ErrorBody,
    "description": "`validation_error` (with `fields`) or `unknown_geo`.",
}
ERROR_502: dict[str, Any] = {
    "model": ErrorBody,
    "description": "`keitaro_bad_gateway` or `keitaro_partial_apply` (with `fields`).",
}
ERROR_504: dict[str, Any] = {
    "model": ErrorBody,
    "description": "`keitaro_timeout`.",
}

RESP_AUTH = {
    401: ERROR_401,
    422: ERROR_422,
}
RESP_PROTECTED = {
    401: ERROR_401,
    422: ERROR_422,
    502: ERROR_502,
    504: ERROR_504,
}
RESP_COMPANY = {
    **RESP_PROTECTED,
    404: ERROR_404,
    409: ERROR_409,
}
