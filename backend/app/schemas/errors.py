from pydantic import BaseModel, Field

from app.errors import ErrorCode


class ErrorBody(BaseModel):
    """Every non-2xx response, including request validation (422), 404/405 and 500.

    Status per `error`: 401 `unauthorized`; 404 `not_found`; 405 `method_not_allowed`;
    409 `name_taken`, `idempotency_conflict`, `company_not_ready`, `campaign_missing`,
    `concurrent_update`, `keitaro_not_found`; 422 `validation_error`, `unknown_geo`;
    500 `internal_error`; 502 `keitaro_bad_gateway`, `keitaro_partial_apply`;
    504 `keitaro_timeout`. Clients branch on `error`, show `message`, and map `fields`
    onto form inputs.
    """

    error: ErrorCode = Field(description="Machine-readable code; fixed HTTP status per code.")
    message: str = Field(
        description="Human-readable explanation, safe to show to the user.",
        examples=["Request validation failed."],
    )
    fields: dict[str, str] | None = Field(
        default=None,
        description=(
            "Per-field messages. Keys are request field paths without the location "
            "prefix (`name`, `geo_codes`, `offers.0.percent`)."
        ),
        examples=[{"name": "Already exists. Pick another name."}],
    )


class HealthOut(BaseModel):
    status: str = Field(description="Service liveness flag.", examples=["ok"])
