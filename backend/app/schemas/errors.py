from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Standard API error payload (`docs/api_contracts.md`)."""

    error: str = Field(
        description=(
            "Machine-readable code: unauthorized, not_found, version_conflict, "
            "name_taken, idempotency_conflict, fetch_blocked, campaign_missing, "
            "validation_error, unknown_geo, keitaro_bad_gateway, keitaro_timeout."
        ),
        examples=["version_conflict"],
    )
    message: str = Field(
        description="Human-readable explanation.",
        examples=["expected_version does not match company.version."],
    )
    fields: dict[str, str] | None = Field(
        default=None,
        description="Optional per-field validation messages (e.g. for name_taken).",
    )


class HealthOut(BaseModel):
    status: str = Field(description="Service liveness flag.", examples=["ok"])
