from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.errors import AppError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_RETRIES = 3
RETRY_BACKOFF = 0.4
CAMPAIGN_PAGE_SIZE = 100
KEITARO_NOT_FOUND = "keitaro_not_found"


@dataclass
class KeitaroOffer:
    offer_id: int
    name: str | None
    share: int = 0
    country: list[str] = field(default_factory=list)


@dataclass
class KeitaroStream:
    stream_id: int
    name: str | None
    position: int
    schema: str | None
    filters_geo: list[str] = field(default_factory=list)
    offers: list[KeitaroOffer] = field(default_factory=list)
    action_type: str | None = None
    action_payload: str | None = None


@dataclass
class KeitaroCampaign:
    campaign_id: int
    name: str
    state: str  # active | disabled
    streams: list[KeitaroStream] = field(default_factory=list)


@dataclass
class KeitaroStats:
    clicks: int | None = None
    uniques: int | None = None
    bots: int | None = None


@dataclass
class CreatedCampaign:
    campaign_id: int
    google_stream_id: int
    offers_stream_id: int


@dataclass
class StreamDraft:
    """Body of Admin API POST /streams. `campaign_id` is set by the caller."""

    name: str
    position: int
    schema: str = "redirect"
    stream_type: str = "regular"
    weight: int = 100
    action_type: str | None = None
    action_payload: str | None = None
    filters_geo: list[str] = field(default_factory=list)
    offers: list[tuple[int, int]] = field(default_factory=list)


class KeitaroClient(ABC):
    domain_id: int | None
    group_id: int | None
    source_id: int | None
    noop: bool

    @abstractmethod
    async def resolve_startup(self) -> None: ...

    @abstractmethod
    async def list_offers(self, q: str | None = None) -> list[KeitaroOffer]: ...

    @abstractmethod
    async def get_offer(self, offer_id: int) -> KeitaroOffer | None: ...

    @abstractmethod
    async def find_campaign_by_name(self, name: str) -> KeitaroCampaign | None: ...

    @abstractmethod
    async def get_campaign(self, campaign_id: int) -> KeitaroCampaign | None: ...

    @abstractmethod
    async def create_campaign(self, *, name: str) -> KeitaroCampaign:
        """Admin API POST /campaigns."""

    @abstractmethod
    async def create_stream(
        self,
        *,
        campaign_id: int,
        stream: StreamDraft,
    ) -> KeitaroStream:
        """Admin API POST /streams. Call only after the campaign create succeeds."""

    async def create_company_campaign(
        self,
        *,
        name: str,
        geo_codes: list[str],
        offer_id: int,
        google_url: str,
    ) -> CreatedCampaign:
        """Campaign, then google stream, then offers stream. Rolls the campaign back."""
        google_draft = StreamDraft(
            name="google",
            position=1,
            schema="redirect",
            action_type="http",
            action_payload=google_url,
            filters_geo=list(geo_codes),
        )
        offers_draft = StreamDraft(
            name="offers",
            position=2,
            schema="landings",
            action_type="http",
            action_payload="",
            offers=[(offer_id, 100)],
        )
        validate_stream_draft(google_draft)
        validate_stream_draft(offers_draft)
        campaign = await self.create_campaign(name=name)
        if campaign.campaign_id < 1:
            raise AppError(502, "keitaro_bad_gateway", "Keitaro create campaign failed.")
        try:
            google = await self.create_stream(
                campaign_id=campaign.campaign_id,
                stream=google_draft,
            )
            offers = await self.create_stream(
                campaign_id=campaign.campaign_id,
                stream=offers_draft,
            )
        except AppError:
            await self.delete_campaign(campaign.campaign_id)
            raise
        return CreatedCampaign(
            campaign_id=campaign.campaign_id,
            google_stream_id=google.stream_id,
            offers_stream_id=offers.stream_id,
        )

    @abstractmethod
    async def delete_campaign(self, campaign_id: int) -> None: ...

    @abstractmethod
    async def update_stream_offers(
        self,
        *,
        campaign_id: int,
        stream_id: int,
        offers: list[tuple[int, int]],
    ) -> None: ...

    @abstractmethod
    async def update_google_geo(
        self,
        *,
        campaign_id: int,
        stream_id: int,
        geo_codes: list[str],
    ) -> None: ...

    @abstractmethod
    async def enable_campaign(self, campaign_id: int) -> None: ...

    @abstractmethod
    async def disable_campaign(self, campaign_id: int) -> None: ...

    @abstractmethod
    async def get_stats(self, campaign_id: int) -> KeitaroStats: ...

    @abstractmethod
    async def aclose(self) -> None: ...


class NoopKeitaroClient(KeitaroClient):
    """Local/dev stub when KEITARO_URL is empty. Does not call the network."""

    def __init__(self) -> None:
        self.domain_id = 1
        self.group_id = 1
        self.source_id = 1
        self.noop = True
        self._campaigns: dict[int, KeitaroCampaign] = {}
        # Catalog is empty in noop: GET /offers must not invent Keitaro rows.
        # get_offer / create may still synthesize ids for offline company tests.
        self._offers: dict[int, KeitaroOffer] = {}
        # Avoid collisions after process restart when DB already has prior mock ids.
        base = int(time.time()) % 1_000_000_000
        self._campaign_ids = itertools.count(base + 1)
        self._stream_ids = itertools.count(base + 10_000)

    async def resolve_startup(self) -> None:
        logger.warning("KEITARO_URL empty — NoopKeitaroClient (mock mode)")

    async def list_offers(self, q: str | None = None) -> list[KeitaroOffer]:
        # No local catalog stub — real list comes from HttpKeitaroClient GET /offers.
        _ = q
        return []

    async def get_offer(self, offer_id: int) -> KeitaroOffer | None:
        return self._offers.get(offer_id) or KeitaroOffer(
            offer_id=offer_id, name=f"Offer {offer_id}"
        )

    async def find_campaign_by_name(self, name: str) -> KeitaroCampaign | None:
        for camp in self._campaigns.values():
            if camp.name.lower() == name.lower():
                return camp
        return None

    async def get_campaign(self, campaign_id: int) -> KeitaroCampaign | None:
        return self._campaigns.get(campaign_id)

    async def create_campaign(self, *, name: str) -> KeitaroCampaign:
        cid = next(self._campaign_ids)
        camp = KeitaroCampaign(
            campaign_id=cid,
            name=name,
            state="active",
        )
        self._campaigns[cid] = camp
        return camp

    async def create_stream(
        self,
        *,
        campaign_id: int,
        stream: StreamDraft,
    ) -> KeitaroStream:
        validate_stream_draft(stream)
        camp = self._campaigns.get(campaign_id)
        if camp is None:
            raise AppError(409, "campaign_missing", "Campaign not found in tracker.")
        sid = next(self._stream_ids)
        offers = [
            KeitaroOffer(offer_id=offer_id, name=None, share=share)
            for offer_id, share in stream.offers
        ]
        for offer_id, _share in stream.offers:
            if offer_id not in self._offers:
                self._offers[offer_id] = KeitaroOffer(
                    offer_id=offer_id, name=f"Offer {offer_id}"
                )
        row = KeitaroStream(
            stream_id=sid,
            name=stream.name,
            position=stream.position,
            schema=stream.schema,
            filters_geo=list(stream.filters_geo),
            offers=offers,
            action_type=stream.action_type,
            action_payload=stream.action_payload,
        )
        camp.streams.append(row)
        return row

    async def delete_campaign(self, campaign_id: int) -> None:
        self._campaigns.pop(campaign_id, None)

    async def update_stream_offers(
        self,
        *,
        campaign_id: int,
        stream_id: int,
        offers: list[tuple[int, int]],
    ) -> None:
        camp = self._campaigns.get(campaign_id)
        if camp is None:
            raise AppError(409, "campaign_missing", "Campaign not found in tracker.")
        for stream in camp.streams:
            if stream.stream_id == stream_id:
                stream.offers = [
                    KeitaroOffer(offer_id=oid, name=None, share=share)
                    for oid, share in offers
                ]
                return
        raise AppError(502, "keitaro_bad_gateway", "Stream not found in tracker.")

    async def update_google_geo(
        self,
        *,
        campaign_id: int,
        stream_id: int,
        geo_codes: list[str],
    ) -> None:
        camp = self._campaigns.get(campaign_id)
        if camp is None:
            raise AppError(409, "campaign_missing", "Campaign not found in tracker.")
        for stream in camp.streams:
            if stream.stream_id == stream_id:
                stream.filters_geo = list(geo_codes)
                return
        raise AppError(502, "keitaro_bad_gateway", "Stream not found in tracker.")

    async def enable_campaign(self, campaign_id: int) -> None:
        camp = self._campaigns.get(campaign_id)
        if camp is None:
            raise AppError(409, "campaign_missing", "Campaign not found in tracker.")
        camp.state = "active"

    async def disable_campaign(self, campaign_id: int) -> None:
        camp = self._campaigns.get(campaign_id)
        if camp is None:
            raise AppError(409, "campaign_missing", "Campaign not found in tracker.")
        camp.state = "disabled"

    async def get_stats(self, campaign_id: int) -> KeitaroStats:
        if campaign_id not in self._campaigns:
            return KeitaroStats()
        return KeitaroStats(clicks=0, uniques=0, bots=0)

    async def aclose(self) -> None:
        return None


class HttpKeitaroClient(KeitaroClient):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        domain_name: str,
        group_name: str,
        source_name: str,
    ) -> None:
        self.noop = False
        self.domain_id: int | None = None
        self.group_id: int | None = None
        self.source_id: int | None = None
        self._domain_name = domain_name
        self._group_name = group_name
        self._source_name = source_name
        self._client = httpx.AsyncClient(
            base_url=_normalize_admin_api_base(base_url),
            headers={"Api-Key": api_key, "Accept": "application/json"},
            timeout=DEFAULT_TIMEOUT,
        )
        self._offer_cache: dict[int, KeitaroOffer] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def resolve_startup(self) -> None:
        domains = await self._request("GET", "/domains", retry=True)
        groups = await self._request(
            "GET", "/groups", params={"type": "campaigns"}, retry=True
        )
        sources = await self._request("GET", "/traffic_sources", retry=True)

        self.domain_id = self._find_id(domains, self._domain_name)
        self.group_id = self._find_id(groups, self._group_name)
        self.source_id = self._find_id(sources, self._source_name)
        if self.domain_id is None or self.group_id is None or self.source_id is None:
            raise RuntimeError(
                "Keitaro resolve failed: domain/group/source not found "
                f"(domain={self._domain_name!r} id={self.domain_id}, "
                f"group={self._group_name!r} id={self.group_id}, "
                f"source={self._source_name!r} id={self.source_id})"
            )

    @staticmethod
    def _find_id(items: Any, name: str) -> int | None:
        for item in _as_list(items):
            if isinstance(item, dict) and str(item.get("name", "")).lower() == name.lower():
                return int(item["id"])
        return None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict | None = None,
        retry: bool = False,
    ) -> Any:
        # Retries only when caller opts in (GET / idempotent reads).
        attempts = MAX_RETRIES if retry else 1
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await self._client.request(
                    method, path, json=json, params=params
                )
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
                    continue
                raise AppError(504, "keitaro_timeout", "Keitaro request timed out.") from exc
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt + 1 < attempts:
                    await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
                    continue
                raise AppError(
                    502, "keitaro_bad_gateway", "Keitaro request failed."
                ) from exc

            if response.status_code >= 500 and attempt + 1 < attempts and retry:
                await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
                continue
            if response.status_code >= 400:
                raise _map_keitaro_http_error(response)
            if response.status_code == 204 or not response.content:
                return None
            try:
                return response.json()
            except ValueError as exc:
                raise AppError(
                    502, "keitaro_bad_gateway", "Keitaro returned invalid JSON."
                ) from exc
        raise AppError(502, "keitaro_bad_gateway", "Keitaro request failed.") from last_exc

    async def _list_all_campaigns(self) -> list[dict[str, Any]]:
        """GET /campaigns with limit/offset until a short page."""
        collected: list[dict[str, Any]] = []
        offset = 0
        while True:
            data = await self._request(
                "GET",
                "/campaigns",
                params={"limit": CAMPAIGN_PAGE_SIZE, "offset": offset},
                retry=True,
            )
            page = [row for row in _as_list(data) if isinstance(row, dict)]
            collected.extend(page)
            if len(page) < CAMPAIGN_PAGE_SIZE:
                break
            offset += CAMPAIGN_PAGE_SIZE
        return collected

    async def list_offers(self, q: str | None = None) -> list[KeitaroOffer]:
        """Admin API GET /offers — full catalog (id, name, country)."""
        data = await self._request("GET", "/offers", retry=True)
        items: list[KeitaroOffer] = []
        for row in _as_list(data):
            offer = _parse_offer_row(row)
            if offer is None:
                continue
            self._offer_cache[offer.offer_id] = offer
            items.append(offer)
        if q:
            ql = q.lower()
            items = [o for o in items if o.name and ql in o.name.lower()]
        return items

    async def get_offer(self, offer_id: int) -> KeitaroOffer | None:
        if offer_id in self._offer_cache:
            return self._offer_cache[offer_id]
        try:
            data = await self._request("GET", f"/offers/{offer_id}", retry=True)
        except AppError as exc:
            if exc.error == KEITARO_NOT_FOUND:
                return None
            raise
        offer = _parse_offer_row(data)
        if offer is None:
            return None
        self._offer_cache[offer_id] = offer
        return offer

    async def find_campaign_by_name(self, name: str) -> KeitaroCampaign | None:
        for row in await self._list_all_campaigns():
            if str(row.get("name", "")).lower() == name.lower():
                return await self.get_campaign(int(row["id"]))
        return None

    async def get_campaign(self, campaign_id: int) -> KeitaroCampaign | None:
        try:
            data = await self._request("GET", f"/campaigns/{campaign_id}", retry=True)
        except AppError as exc:
            if exc.error == KEITARO_NOT_FOUND:
                return None
            raise
        if not data or not isinstance(data, dict):
            return None
        streams_raw = await self._request(
            "GET", f"/campaigns/{campaign_id}/streams", retry=True
        )
        streams = [
            self._parse_stream(s)
            for s in _as_list(streams_raw)
            if isinstance(s, dict)
        ]
        state = "active"
        if data.get("state") == "disabled" or data.get("status") == "disabled":
            state = "disabled"
        return KeitaroCampaign(
            campaign_id=int(data["id"]),
            name=str(data.get("name", "")),
            state=state,
            streams=streams,
        )

    def _parse_stream(self, raw: dict) -> KeitaroStream:
        """Parse Stream; schema stays API enum (landings|redirect|action)."""
        filters_geo: list[str] = []
        for filt in raw.get("filters") or []:
            if not isinstance(filt, dict):
                continue
            if filt.get("name") in ("country", "geo"):
                filters_geo = _parse_filter_payload(filt.get("payload"))
        offers: list[KeitaroOffer] = []
        for offer in raw.get("offers") or []:
            if not isinstance(offer, dict):
                continue
            # OfferStream: offer_id + share (legacy: id / percent).
            if "offer_id" in offer:
                oid = int(offer["offer_id"])
            elif "id" in offer:
                oid = int(offer["id"])
            else:
                continue
            share_raw = offer.get("share")
            if share_raw is None:
                share_raw = offer.get("percent")
            offers.append(
                KeitaroOffer(
                    offer_id=oid,
                    name=offer.get("name"),
                    share=int(share_raw or 0),
                )
            )
        action_payload = raw.get("action_payload")
        if action_payload is not None and not isinstance(action_payload, str):
            action_payload = json.dumps(action_payload)
        return KeitaroStream(
            stream_id=int(raw["id"]),
            name=raw.get("name"),
            position=int(raw.get("position") or raw.get("order") or 0),
            # Keep API value; offers-flow is detected by offers[] / name elsewhere.
            schema=raw.get("schema"),
            filters_geo=filters_geo,
            offers=offers,
            action_type=raw.get("action_type"),
            action_payload=action_payload,
        )

    async def create_campaign(self, *, name: str) -> KeitaroCampaign:
        raw = await self._request(
            "POST",
            "/campaigns",
            json={
                "name": name,
                "alias": name.lower().replace(" ", "_")[:32],
                "type": "position",
                "domain_id": self.domain_id,
                "group_id": self.group_id,
                "traffic_source_id": self.source_id,
                "state": "active",
            },
        )
        if not isinstance(raw, dict) or "id" not in raw:
            raise AppError(502, "keitaro_bad_gateway", "Keitaro create campaign failed.")
        state = "active"
        if raw.get("state") == "disabled" or raw.get("status") == "disabled":
            state = "disabled"
        return KeitaroCampaign(
            campaign_id=int(raw["id"]),
            name=str(raw.get("name") or name),
            state=state,
        )

    async def create_stream(
        self,
        *,
        campaign_id: int,
        stream: StreamDraft,
    ) -> KeitaroStream:
        validate_stream_draft(stream)
        raw = await self._request(
            "POST",
            "/streams",
            json=_stream_body(campaign_id, stream),
        )
        if not isinstance(raw, dict) or "id" not in raw:
            raise AppError(502, "keitaro_bad_gateway", "Keitaro create stream failed.")
        return self._parse_stream(raw)

    async def delete_campaign(self, campaign_id: int) -> None:
        await self._request("DELETE", f"/campaigns/{campaign_id}")

    async def update_stream_offers(
        self,
        *,
        campaign_id: int,
        stream_id: int,
        offers: list[tuple[int, int]],
    ) -> None:
        # Admin API: PUT /streams/{id} (not /campaigns/{id}/streams/{id}).
        await self._request(
            "PUT",
            f"/streams/{stream_id}",
            json={
                "campaign_id": campaign_id,
                "offers": [
                    {"offer_id": oid, "share": share, "state": "active"}
                    for oid, share in offers
                ],
            },
            retry=True,
        )

    async def update_google_geo(
        self,
        *,
        campaign_id: int,
        stream_id: int,
        geo_codes: list[str],
    ) -> None:
        """Update country filter on the google stream; BE persists company_geo after."""
        await self._request(
            "PUT",
            f"/streams/{stream_id}",
            json={
                "campaign_id": campaign_id,
                "filters": [
                    {
                        "name": "country",
                        "mode": "accept",
                        "payload": list(geo_codes),
                    }
                ],
            },
        )

    async def enable_campaign(self, campaign_id: int) -> None:
        await self._request("POST", f"/campaigns/{campaign_id}/enable")

    async def disable_campaign(self, campaign_id: int) -> None:
        await self._request("POST", f"/campaigns/{campaign_id}/disable")

    async def get_stats(self, campaign_id: int) -> KeitaroStats:
        try:
            data = await self._request(
                "POST",
                "/report/build",
                json={
                    "range": {"interval": "all_time"},
                    "dimensions": [],
                    "metrics": ["clicks", "campaign_unique_clicks", "bots"],
                    "filters": [
                        {
                            "name": "campaign_id",
                            "operator": "EQUALS",
                            "expression": campaign_id,
                        }
                    ],
                },
                retry=True,
            )
        except AppError:
            return KeitaroStats()
        rows = (data or {}).get("rows") or []
        if not rows:
            return KeitaroStats(clicks=0, uniques=0, bots=0)
        row = rows[0]
        return KeitaroStats(
            clicks=_as_int(row.get("clicks")),
            uniques=_as_int(row.get("campaign_unique_clicks") or row.get("uniques")),
            bots=_as_int(row.get("bots")),
        )


def validate_stream_draft(stream: StreamDraft) -> None:
    if stream.name == "google" and not stream.filters_geo:
        raise AppError(
            422,
            "validation_error",
            "Google stream requires a geo list.",
            fields={"geo_codes": "Add at least one geo code."},
        )
    if stream.name != "offers":
        return
    if not stream.offers:
        raise AppError(
            422,
            "validation_error",
            "Offers stream requires at least one offer.",
            fields={"offer_id": "Pick an offer."},
        )
    for offer_id, _share in stream.offers:
        if offer_id < 1:
            raise AppError(
                422,
                "validation_error",
                "Offers stream requires at least one offer.",
                fields={"offer_id": "Pick an offer."},
            )


def _stream_body(campaign_id: int, stream: StreamDraft) -> dict[str, Any]:
    body: dict[str, Any] = {
        "campaign_id": campaign_id,
        "name": stream.name,
        "type": stream.stream_type,
        "position": stream.position,
        "weight": stream.weight,
        "schema": stream.schema,
        "action_type": stream.action_type or "http",
        "filters": [],
        "offers": [
            {"offer_id": offer_id, "share": share, "state": "active"}
            for offer_id, share in stream.offers
        ],
    }
    if stream.filters_geo:
        body["filters"] = [
            {
                "name": "country",
                "mode": "accept",
                "payload": list(stream.filters_geo),
            }
        ]
    if stream.action_payload is not None:
        body["action_payload"] = stream.action_payload
    return body


def _normalize_admin_api_base(base_url: str) -> str:
    """Ensure httpx base ends with `/admin_api/v1` (tolerate bare host or `/v1`)."""
    root = base_url.strip().rstrip("/")
    if root.endswith("/admin_api/v1"):
        return root
    if root.endswith("/admin_api"):
        return f"{root}/v1"
    if root.endswith("/v1"):
        # e.g. https://host:8105/v1 → https://host:8105/admin_api/v1
        return f"{root[: -len('/v1')]}/admin_api/v1"
    return f"{root}/admin_api/v1"


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[Any]:
    """Normalize Keitaro list responses (bare array or wrapped object)."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("rows", "data", "items", "offers", "campaigns", "streams"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
        if "id" in value:
            return [value]
    return []


def _parse_country(value: Any) -> list[str]:
    """Offer.country is string[] in Admin API; tolerate CSV / single string."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        return [part.strip() for part in text.split(",") if part.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _parse_offer_row(row: Any) -> KeitaroOffer | None:
    """Map Admin API Offer object → KeitaroOffer."""
    if not isinstance(row, dict) or "id" not in row:
        return None
    name = row.get("name")
    return KeitaroOffer(
        offer_id=int(row["id"]),
        name=str(name) if name is not None else None,
        country=_parse_country(row.get("country")),
    )


def _parse_filter_payload(payload: Any) -> list[str]:
    """Filter.payload is a string in OpenAPI (CSV or JSON-array string)."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [str(p).strip() for p in payload if str(p).strip()]
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [str(p).strip() for p in parsed if str(p).strip()]
        return [part.strip() for part in text.split(",") if part.strip()]
    return [str(payload).strip()] if str(payload).strip() else []


def _keitaro_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        err = body.get("error")
        if err:
            return str(err)
        message = body.get("message")
        if message:
            return str(message)
    text = (response.text or "").strip()
    if text:
        return text[:300]
    return f"Keitaro responded with {response.status_code}."


def _map_keitaro_http_error(response: httpx.Response) -> AppError:
    message = _keitaro_error_message(response)
    if response.status_code == 404:
        # Distinguishable so GET helpers can return None; still 502 to API.
        return AppError(502, KEITARO_NOT_FOUND, message)
    return AppError(502, "keitaro_bad_gateway", message)


_keitaro_singleton: KeitaroClient | None = None


def _load_repo_dotenv() -> None:
    """Best-effort load of repo-root `.env` without overriding existing env."""
    try:
        root = Path(__file__).resolve().parents[3]
    except IndexError:
        return
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def build_keitaro_client() -> KeitaroClient:
    _load_repo_dotenv()
    url = (os.environ.get("KEITARO_URL") or "").strip()
    if not url:
        return NoopKeitaroClient()
    return HttpKeitaroClient(
        base_url=url,
        api_key=os.environ.get("KEITARO_API_KEY", ""),
        domain_name=os.environ.get("KEITARO_DOMAIN", ""),
        group_name=os.environ.get("KEITARO_GROUP", ""),
        source_name=os.environ.get("KEITARO_SOURCE", ""),
    )


def get_keitaro_singleton() -> KeitaroClient:
    global _keitaro_singleton
    if _keitaro_singleton is None:
        _keitaro_singleton = build_keitaro_client()
    return _keitaro_singleton


async def init_keitaro() -> KeitaroClient:
    client = get_keitaro_singleton()
    await client.resolve_startup()
    return client


async def shutdown_keitaro() -> None:
    global _keitaro_singleton
    if _keitaro_singleton is not None:
        await _keitaro_singleton.aclose()
        _keitaro_singleton = None
