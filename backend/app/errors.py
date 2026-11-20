import logging
from enum import StrEnum
from http import HTTPStatus
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    """Machine-readable `error` values. Status is fixed per code (see `ERROR_STATUS`)."""

    unauthorized = "unauthorized"
    not_found = "not_found"
    method_not_allowed = "method_not_allowed"
    name_taken = "name_taken"
    idempotency_conflict = "idempotency_conflict"
    company_not_ready = "company_not_ready"
    campaign_missing = "campaign_missing"
    concurrent_update = "concurrent_update"
    keitaro_not_found = "keitaro_not_found"
    validation_error = "validation_error"
    unknown_geo = "unknown_geo"
    keitaro_bad_gateway = "keitaro_bad_gateway"
    keitaro_partial_apply = "keitaro_partial_apply"
    keitaro_timeout = "keitaro_timeout"
    internal_error = "internal_error"


ERROR_STATUS: dict[ErrorCode, int] = {
    ErrorCode.unauthorized: 401,
    ErrorCode.not_found: 404,
    ErrorCode.method_not_allowed: 405,
    ErrorCode.name_taken: 409,
    ErrorCode.idempotency_conflict: 409,
    ErrorCode.company_not_ready: 409,
    ErrorCode.campaign_missing: 409,
    ErrorCode.concurrent_update: 409,
    ErrorCode.keitaro_not_found: 409,
    ErrorCode.validation_error: 422,
    ErrorCode.unknown_geo: 422,
    ErrorCode.keitaro_bad_gateway: 502,
    ErrorCode.keitaro_partial_apply: 502,
    ErrorCode.keitaro_timeout: 504,
    ErrorCode.internal_error: 500,
}


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        error: ErrorCode | str,
        message: str,
        fields: dict[str, str] | None = None,
    ) -> None:
        self.error = ErrorCode(error)
        expected = ERROR_STATUS[self.error]
        if status_code != expected:
            raise ValueError(f"{self.error} must use HTTP {expected}, got {status_code}")
        self.status_code = status_code
        self.message = message
        self.fields = fields
        super().__init__(message)


def error_body(
    error: ErrorCode, message: str, fields: dict[str, str] | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"error": error.value, "message": message}
    if fields:
        body["fields"] = fields
    return body


def _validation_fields(exc: RequestValidationError) -> dict[str, str]:
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", ())]
        key = ".".join(loc[1:]) if len(loc) > 1 else (loc[0] if loc else "request")
        fields.setdefault(key, str(err.get("msg", "Invalid value.")))
    return fields


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.error, exc.message, exc.fields),
    )


async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body(
            ErrorCode.validation_error,
            "Request validation failed.",
            _validation_fields(exc),
        ),
    )


async def http_error_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = {
        401: ErrorCode.unauthorized,
        404: ErrorCode.not_found,
        405: ErrorCode.method_not_allowed,
        422: ErrorCode.validation_error,
    }.get(exc.status_code, ErrorCode.internal_error)
    detail = exc.detail if isinstance(exc.detail, str) else None
    message = detail or HTTPStatus(exc.status_code).phrase
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, message),
        headers=getattr(exc, "headers", None),
    )


async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=error_body(ErrorCode.internal_error, "Internal server error."),
    )
