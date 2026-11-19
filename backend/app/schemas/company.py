from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import CompanyLifecycle, StreamType, TrafficStatus


class OfferRow(BaseModel):
    offer_id: int
    name: str | None = None
    percent: int
    pinned: bool
    removed: bool
    position: int


class StreamOut(BaseModel):
    id: int
    type: StreamType
    position: int
    sync: Literal["synced", "update_mode"] | None = None
    offers: list[OfferRow] = Field(default_factory=list)


class DriftOut(BaseModel):
    campaign_missing: bool = False
    offers: bool = False
    geo: bool = False
    traffic: bool = False
    streams: bool = False


class CompanyOut(BaseModel):
    id: int
    name: str
    lifecycle: CompanyLifecycle
    version: int
    traffic_status: TrafficStatus
    geo_codes: list[str] = Field(default_factory=list)
    sync: Literal["synced", "update_mode"] | None = None
    streams: list[StreamOut] = Field(default_factory=list)
    drift: DriftOut | None = None
    reconcile_unavailable: bool = False


class CompanyListItem(BaseModel):
    id: int
    name: str
    lifecycle: CompanyLifecycle
    traffic_status: TrafficStatus
    sync: Literal["synced", "update_mode"] | None = None
    version: int


class CompanyListResponse(BaseModel):
    items: list[CompanyListItem]
    page: int
    page_size: int
    total: int


class CreateCompanyRequest(BaseModel):
    name: str
    geo_codes: list[str] = Field(min_length=1)
    offer_id: int


class StreamActionRequest(BaseModel):
    action: Literal["add", "remove", "restore", "pin", "unpin", "set_percent"]
    offer_id: int
    percent: int | None = None
    expected_version: int


class GeoPatchRequest(BaseModel):
    geo_codes: list[str] = Field(min_length=1)
    expected_version: int


class VersionBody(BaseModel):
    expected_version: int


class StatsOut(BaseModel):
    clicks: int | None = None
    uniques: int | None = None
    bots: int | None = None


class OfferCatalogItem(BaseModel):
    offer_id: int
    name: str | None = None


class OfferCatalogResponse(BaseModel):
    items: list[OfferCatalogItem]
