from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        fields: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error = error
        self.message = message
        self.fields = fields
        super().__init__(message)


def error_body(error: str, message: str, fields: dict[str, str] | None = None) -> dict:
    body: dict = {"error": error, "message": message}
    if fields:
        body["fields"] = fields
    return body


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.error, exc.message, exc.fields),
    )
