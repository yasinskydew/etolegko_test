from pydantic import BaseModel, Field

from app.models.enums import CompanyLifecycle, StreamType, TrafficStatus


class OfferRow(BaseModel):
    """Offer row in an `offers` stream."""

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
    name: str = Field(
        description="Company name as stored and sent to Keitaro. Create requires the test_yasinsky_company prefix."
    )
    lifecycle: CompanyLifecycle = Field(description="`creating` | `ready`.")
    traffic_status: TrafficStatus = Field(description="`active` | `disabled`.")
    geo_codes: list[str] = Field(
        default_factory=list,
        description="Ordered geo codes from `company_geo`.",
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
    traffic_status: TrafficStatus = Field(
        description="DB `company.traffic_status` (enable/disable). Not read from Keitaro on list."
    )
    geo_codes: list[str] = Field(
        default_factory=list,
        description="Ordered codes from `company_geo`.",
    )


class CompanyListResponse(BaseModel):
    items: list[CompanyListItem]
    page: int = Field(description="1-based page index.")
    page_size: int
    total: int = Field(description="Total matching companies.")


class CreateCompanyRequest(BaseModel):
    """Create company + Keitaro campaign with google + offers streams."""

    name: str = Field(
        description=(
            "Must start with `test_yasinsky_company`. "
            "1–64 chars `[a-zA-Z0-9_\\- ]`, no leading/trailing spaces."
        ),
        examples=["test_yasinsky_company"],
    )
    geo_codes: list[str] = Field(
        min_length=1,
        description="Non-empty unique 2-letter codes present in `geo`.",
        examples=[["MX", "AU", "RO"]],
    )
    offer_id: int = Field(
        ge=1,
        description="Initial offers-stream participant; at least one offer, gets 100% share.",
        examples=[3749],
    )


class OfferApplyRow(BaseModel):
    offer_id: int
    percent: int = Field(ge=0, le=100)
    pinned: bool = False
    removed: bool = False
    position: int = Field(ge=1)


class CompanyApplyRequest(BaseModel):
    """Full desired company state for Push (DB + Keitaro)."""

    geo_codes: list[str] = Field(min_length=1)
    offers: list[OfferApplyRow] = Field(
        description="Full offers-stream rows including archive (`removed`).",
    )


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
