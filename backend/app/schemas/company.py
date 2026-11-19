from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import CompanyLifecycle, StreamType, TrafficStatus


class OfferRow(BaseModel):
    """Offer row in the working copy of an `offers` stream."""

    offer_id: int = Field(description="Keitaro offer id.")
    name: str | None = Field(
        default=None,
        description="Display name from catalog cache; `null` if unknown.",
    )
    percent: int = Field(
        description="Share 0..100. For `removed=true` UI shows 0%; stored value is last share."
    )
    pinned: bool = Field(description="Pinned offers keep their percent during redistribute.")
    removed: bool = Field(description="Archive flag; archived rows survive Push.")
    position: int = Field(description="1-based order in the stream.")


class StreamOut(BaseModel):
    """Stream attached to a company."""

    id: int = Field(description="Local stream id.")
    type: StreamType = Field(description="`google` | `offers` | `plain`.")
    position: int = Field(description="1-based stream order (`google`=1, `offers`=2).")
    sync: Literal["synced", "update_mode"] | None = Field(
        default=None,
        description=(
            "Computed for `offers` only: working copy vs snapshot. "
            "`null` for `google`/`plain`."
        ),
    )
    offers: list[OfferRow] = Field(
        default_factory=list,
        description="Empty for `google`/`plain`. Includes archive rows for `offers`.",
    )


class DriftOut(BaseModel):
    """Drift vs Keitaro, computed on company card read. Not stored in DB."""

    campaign_missing: bool = False
    offers: bool = False
    geo: bool = False
    traffic: bool = False
    streams: bool = False


class CompanyOut(BaseModel):
    """Full company card / editor payload."""

    id: int
    name: str = Field(description="Company name as stored and sent to Keitaro (no prefix).")
    lifecycle: CompanyLifecycle = Field(description="`creating` | `ready`.")
    version: int = Field(description="Optimistic lock counter; send as expected_version.")
    traffic_status: TrafficStatus = Field(description="`active` | `disabled`.")
    geo_codes: list[str] = Field(
        default_factory=list,
        description="Ordered geo codes from `company_geo`.",
    )
    sync: Literal["synced", "update_mode"] | None = Field(
        default=None,
        description="Sync status of the `offers` stream; `null` while `creating`.",
    )
    streams: list[StreamOut] = Field(default_factory=list)
    drift: DriftOut | None = Field(
        default=None,
        description="`null` when `reconcile_unavailable` is true.",
    )
    reconcile_unavailable: bool = Field(
        default=False,
        description="True when Keitaro could not be reached for drift calculation.",
    )


class CompanyListItem(BaseModel):
    """Row in the companies list."""

    id: int
    name: str
    lifecycle: CompanyLifecycle
    traffic_status: TrafficStatus
    sync: Literal["synced", "update_mode"] | None = None
    version: int


class CompanyListResponse(BaseModel):
    items: list[CompanyListItem]
    page: int = Field(description="1-based page index.")
    page_size: int
    total: int = Field(description="Total matching companies.")


class CreateCompanyRequest(BaseModel):
    """Create company + Keitaro campaign with google + offers streams."""

    name: str = Field(
        description="1–64 chars `[a-zA-Z0-9_\\- ]`, no leading/trailing spaces.",
        examples=["mx_beauty"],
    )
    geo_codes: list[str] = Field(
        min_length=1,
        description="Non-empty list of codes present in `geo` table.",
        examples=[["MX", "AU", "RO"]],
    )
    offer_id: int = Field(
        description="Initial offers-stream participant; gets 100% share.",
        examples=[3749],
    )


class StreamActionRequest(BaseModel):
    """Single editor action on an `offers` stream (not the final composition)."""

    action: Literal["add", "remove", "restore", "pin", "unpin", "set_percent"] = Field(
        description=(
            "`add` of an archived offer is treated as `restore`. "
            "`percent` is required only for `set_percent`."
        ),
    )
    offer_id: int
    percent: int | None = Field(
        default=None,
        description="Required for `set_percent` (1–100); omit otherwise.",
    )
    expected_version: int = Field(description="Must equal current `company.version`.")


class GeoPatchRequest(BaseModel):
    """Update geo via Keitaro-first write on the google stream filter."""

    geo_codes: list[str] = Field(min_length=1, description="Replacement ordered geo list.")
    expected_version: int


class VersionBody(BaseModel):
    """Body for enable/disable traffic toggles."""

    expected_version: int = Field(description="Must equal current `company.version`.")


class StatsOut(BaseModel):
    """Keitaro campaign stats; not persisted."""

    clicks: int | None = None
    uniques: int | None = None
    bots: int | None = None


class OfferCatalogItem(BaseModel):
    offer_id: int
    name: str | None = None
    country: list[str] = Field(
        default_factory=list,
        description="Keitaro Offer.country codes (Admin API string[]).",
    )


class OfferCatalogResponse(BaseModel):
    items: list[OfferCatalogItem] = Field(
        description="Catalog entries from Keitaro Admin API GET /offers."
    )
