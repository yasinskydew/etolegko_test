from __future__ import annotations

from app.clients.keitaro import KeitaroCampaign, KeitaroClient
from app.models import Company, Stream, StreamType
from app.schemas.company import (
    CompanyListItem,
    CompanyOut,
    DriftOut,
    OfferRow,
    StreamOut,
)


def _offer_name(cache: dict[int, str | None], offer_id: int) -> str | None:
    return cache.get(offer_id)


def map_stream(
    stream: Stream,
    name_cache: dict[int, str | None],
) -> StreamOut:
    offers = [
        OfferRow(
            offer_id=o.offer_id,
            name=_offer_name(name_cache, o.offer_id),
            percent=int(o.percent),
            pinned=bool(o.pinned),
            removed=bool(o.removed),
            position=int(o.position),
        )
        for o in sorted(stream.offers, key=lambda x: x.position)
    ]
    return StreamOut(
        id=stream.id,
        type=stream.type,
        position=stream.position,
        offers=offers if stream.type == StreamType.offers else [],
    )


def map_company_list_item(company: Company) -> CompanyListItem:
    geo_codes = [g.geo_code for g in sorted(company.geos, key=lambda x: x.position)]
    return CompanyListItem(
        id=company.id,
        name=company.name,
        lifecycle=company.lifecycle,
        traffic_status=company.traffic_status,
        geo_codes=geo_codes,
    )


def map_company(
    company: Company,
    *,
    name_cache: dict[int, str | None] | None = None,
    drift: DriftOut | None = None,
    reconcile_unavailable: bool = False,
) -> CompanyOut:
    cache = name_cache or {}
    geo_codes = [g.geo_code for g in sorted(company.geos, key=lambda x: x.position)]
    streams = [
        map_stream(s, cache)
        for s in sorted(company.streams, key=lambda x: x.position)
    ]
    return CompanyOut(
        id=company.id,
        name=company.name,
        lifecycle=company.lifecycle,
        traffic_status=company.traffic_status,
        geo_codes=geo_codes,
        streams=streams,
        drift=None if reconcile_unavailable else drift,
        reconcile_unavailable=reconcile_unavailable,
    )


def compute_drift(
    company: Company,
    campaign: KeitaroCampaign | None,
) -> DriftOut:
    if campaign is None:
        return DriftOut(campaign_missing=True)

    drift = DriftOut()
    our_geo = [g.geo_code for g in sorted(company.geos, key=lambda x: x.position)]
    google = next((s for s in company.streams if s.type == StreamType.google), None)
    k_google = None
    if google and google.keitaro_stream_id:
        k_google = next(
            (s for s in campaign.streams if s.stream_id == google.keitaro_stream_id),
            None,
        )
    if k_google is not None and sorted(k_google.filters_geo) != sorted(our_geo):
        drift.geo = True

    expected_traffic = (
        "active" if company.traffic_status.value == "active" else "disabled"
    )
    if campaign.state != expected_traffic:
        drift.traffic = True

    offers_stream = next(
        (s for s in company.streams if s.type == StreamType.offers), None
    )
    k_offers = None
    if offers_stream and offers_stream.keitaro_stream_id:
        k_offers = next(
            (
                s
                for s in campaign.streams
                if s.stream_id == offers_stream.keitaro_stream_id
            ),
            None,
        )
    if offers_stream is not None:
        our_active = {
            (o.offer_id, int(o.percent))
            for o in offers_stream.offers
            if not o.removed
        }
        their_active = {
            (o.offer_id, int(o.share)) for o in (k_offers.offers if k_offers else [])
        }
        if our_active != their_active:
            drift.offers = True

    our_plain_ids = {
        s.keitaro_stream_id
        for s in company.streams
        if s.type == StreamType.plain and s.keitaro_stream_id is not None
    }
    known_ids = {
        s.keitaro_stream_id
        for s in company.streams
        if s.keitaro_stream_id is not None
    }
    their_ids = {s.stream_id for s in campaign.streams}
    if google and google.keitaro_stream_id and google.keitaro_stream_id not in their_ids:
        drift.streams = True
    if (
        offers_stream
        and offers_stream.keitaro_stream_id
        and offers_stream.keitaro_stream_id not in their_ids
    ):
        drift.streams = True
    extra_plain = their_ids - known_ids
    missing_plain = our_plain_ids - their_ids
    if extra_plain or missing_plain:
        drift.streams = True

    return drift


async def build_name_cache(
    keitaro: KeitaroClient,
    company: Company,
) -> dict[int, str | None]:
    cache: dict[int, str | None] = {}
    offer_ids: set[int] = set()
    for stream in company.streams:
        for offer in stream.offers:
            offer_ids.add(offer.offer_id)
    for offer_id in offer_ids:
        offer = await keitaro.get_offer(offer_id)
        cache[offer_id] = offer.name if offer else None
    return cache