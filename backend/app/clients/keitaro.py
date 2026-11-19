from __future__ import annotations

import asyncio
import logging
import os
import itertools
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.errors import AppError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_RETRIES = 3
RETRY_BACKOFF = 0.4


@dataclass
class KeitaroOffer:
    offer_id: int
    name: str | None
    share: int = 0


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
    async def create_company_campaign(
        self,
        *,
        name: str,
        geo_codes: list[str],
        offer_id: int,
        google_url: str,
    ) -> CreatedCampaign: ...

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
        self._offers: dict[int, KeitaroOffer] = {
            3749: KeitaroOffer(offer_id=3749, name="Miaflow BEAUTY"),
            3801: KeitaroOffer(offer_id=3801, name="Demo Offer 2"),
        }
        # Avoid collisions after process restart when DB already has prior mock ids.
        base = int(time.time()) % 1_000_000_000
        self._campaign_ids = itertools.count(base + 1)
        self._stream_ids = itertools.count(base + 10_000)

    async def resolve_startup(self) -> None:
        logger.warning("KEITARO_URL empty — NoopKeitaroClient (mock mode)")

    async def list_offers(self, q: str | None = None) -> list[KeitaroOffer]:
        items = list(self._offers.values())
        if q:
            ql = q.lower()
            items = [o for o in items if o.name and ql in o.name.lower()]
        return items

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

    async def create_company_campaign(
        self,
        *,
        name: str,
        geo_codes: list[str],
        offer_id: int,
        google_url: str,
    ) -> CreatedCampaign:
        cid = next(self._campaign_ids)
        gid = next(self._stream_ids)
        oid = next(self._stream_ids)
        camp = KeitaroCampaign(
            campaign_id=cid,
            name=name,
            state="active",
            streams=[
                KeitaroStream(
                    stream_id=gid,
                    name="google",
                    position=1,
                    schema="action",
                    filters_geo=list(geo_codes),
                    action_type="http",
                    action_payload=google_url,
                ),
                KeitaroStream(
                    stream_id=oid,
                    name="offers",
                    position=2,
                    schema="offers",
                    offers=[KeitaroOffer(offer_id=offer_id, name=None, share=100)],
                ),
            ],
        )
        self._campaigns[cid] = camp
        if offer_id not in self._offers:
            self._offers[offer_id] = KeitaroOffer(
                offer_id=offer_id, name=f"Offer {offer_id}"
            )
        return CreatedCampaign(
            campaign_id=cid,
            google_stream_id=gid,
            offers_stream_id=oid,
        )

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
        root = base_url.rstrip("/")
        if not root.endswith("/admin_api/v1"):
            root = f"{root}/admin_api/v1"
        self._client = httpx.AsyncClient(
            base_url=root,
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
        if not isinstance(items, list):
            return None
        for item in items:
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
                raise AppError(
                    502,
                    "keitaro_bad_gateway",
                    f"Keitaro responded with {response.status_code}.",
                )
            if response.status_code == 204 or not response.content:
                return None
            return response.json()
        raise AppError(502, "keitaro_bad_gateway", "Keitaro request failed.") from last_exc

    async def list_offers(self, q: str | None = None) -> list[KeitaroOffer]:
        data = await self._request("GET", "/offers", retry=True)
        items: list[KeitaroOffer] = []
        for row in data or []:
            offer = KeitaroOffer(
                offer_id=int(row["id"]),
                name=row.get("name"),
            )
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
        except AppError:
            return None
        if not data:
            return None
        offer = KeitaroOffer(offer_id=int(data["id"]), name=data.get("name"))
        self._offer_cache[offer_id] = offer
        return offer

    async def find_campaign_by_name(self, name: str) -> KeitaroCampaign | None:
        data = await self._request("GET", "/campaigns", retry=True)
        for row in data or []:
            if str(row.get("name", "")).lower() == name.lower():
                return await self.get_campaign(int(row["id"]))
        return None

    async def get_campaign(self, campaign_id: int) -> KeitaroCampaign | None:
        try:
            data = await self._request("GET", f"/campaigns/{campaign_id}", retry=True)
        except AppError as exc:
            if "404" in exc.message or "not found" in exc.message.lower():
                return None
            # Keitaro may return 502 for missing; try streams endpoint
            try:
                await self._request(
                    "GET", f"/campaigns/{campaign_id}/streams", retry=True
                )
            except AppError:
                return None
            return None
        if not data:
            return None
        streams_raw = await self._request(
            "GET", f"/campaigns/{campaign_id}/streams", retry=True
        )
        streams = [self._parse_stream(s) for s in streams_raw or []]
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
        filters_geo: list[str] = []
        for filt in raw.get("filters") or []:
            if filt.get("name") == "country" or filt.get("name") == "geo":
                payload = filt.get("payload") or []
                if isinstance(payload, str):
                    filters_geo = [p.strip() for p in payload.split(",") if p.strip()]
                elif isinstance(payload, list):
                    filters_geo = [str(p) for p in payload]
        offers: list[KeitaroOffer] = []
        for offer in raw.get("offers") or []:
            share = int(offer.get("share") or offer.get("percent") or 0)
            offers.append(
                KeitaroOffer(
                    offer_id=int(offer["offer_id"] if "offer_id" in offer else offer["id"]),
                    name=offer.get("name"),
                    share=share,
                )
            )
        return KeitaroStream(
            stream_id=int(raw["id"]),
            name=raw.get("name"),
            position=int(raw.get("position") or raw.get("order") or 0),
            schema=raw.get("schema"),
            filters_geo=filters_geo,
            offers=offers,
            action_type=raw.get("action_type"),
            action_payload=raw.get("action_payload"),
        )

    async def create_company_campaign(
        self,
        *,
        name: str,
        geo_codes: list[str],
        offer_id: int,
        google_url: str,
    ) -> CreatedCampaign:
        campaign = await self._request(
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
        campaign_id = int(campaign["id"])
        try:
            google = await self._request(
                "POST",
                f"/campaigns/{campaign_id}/streams",
                json={
                    "campaign_id": campaign_id,
                    "name": "google",
                    "type": "regular",
                    "position": 1,
                    "weight": 100,
                    "schema": "action",
                    "action_type": "http",
                    "action_payload": google_url,
                    "filters": [
                        {
                            "name": "country",
                            "mode": "accept",
                            "payload": geo_codes,
                        }
                    ],
                    "offers": [],
                },
            )
            offers = await self._request(
                "POST",
                f"/campaigns/{campaign_id}/streams",
                json={
                    "campaign_id": campaign_id,
                    "name": "offers",
                    "type": "regular",
                    "position": 2,
                    "weight": 100,
                    "schema": "offers",
                    "filters": [],
                    "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
                },
            )
        except AppError:
            await self.delete_campaign(campaign_id)
            raise
        return CreatedCampaign(
            campaign_id=campaign_id,
            google_stream_id=int(google["id"]),
            offers_stream_id=int(offers["id"]),
        )

    async def delete_campaign(self, campaign_id: int) -> None:
        await self._request("DELETE", f"/campaigns/{campaign_id}")

    async def update_stream_offers(
        self,
        *,
        campaign_id: int,
        stream_id: int,
        offers: list[tuple[int, int]],
    ) -> None:
        await self._request(
            "PUT",
            f"/campaigns/{campaign_id}/streams/{stream_id}",
            json={
                "offers": [
                    {"offer_id": oid, "share": share, "state": "active"}
                    for oid, share in offers
                ]
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
        await self._request(
            "PUT",
            f"/campaigns/{campaign_id}/streams/{stream_id}",
            json={
                "filters": [
                    {"name": "country", "mode": "accept", "payload": geo_codes}
                ]
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


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


_keitaro_singleton: KeitaroClient | None = None


def build_keitaro_client() -> KeitaroClient:
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
