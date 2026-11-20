from __future__ import annotations

from app.clients.keitaro import KeitaroCampaign, KeitaroClient, KeitaroStream
from app.errors import AppError
from app.models import Stream, StreamType, TrafficStatus
from app.repositories import UnitOfWork
from app.schemas.company import CompanyOut
from app.services.companies.guard import CompanyWriteGuard
from app.services.companies.queries import CompanyQueryService
from app.services.companies.validator import CompanyValidator
from app.services.company_mapper import to_rows
from app.services.weight_util import OfferWeight


class FetchFromKeitaroUseCase:
    """Pull offers / geo / traffic / plain streams from Keitaro into the local DB."""

    def __init__(
        self,
        uow: UnitOfWork,
        keitaro: KeitaroClient,
        validator: CompanyValidator,
        guard: CompanyWriteGuard,
        queries: CompanyQueryService,
    ) -> None:
        self._uow = uow
        self._keitaro = keitaro
        self._validator = validator
        self._guard = guard
        self._queries = queries

    async def execute(self, company_id: int) -> CompanyOut:
        company = await self._guard.load_ready(company_id)
        campaign_id = self._guard.campaign_id(company)
        token = company.updated_at

        streams = await self._uow.streams.list_by_company(company_id)
        offers_stream = next((s for s in streams if s.type == StreamType.offers), None)
        google_stream = next((s for s in streams if s.type == StreamType.google), None)
        if offers_stream is None:
            raise AppError(404, "not_found", "Offers stream not found.")
        await self._guard.end_read()

        campaign = await self._keitaro.get_campaign(campaign_id)
        if campaign is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")

        weights = self._merge_offers(offers_stream, _tracker_stream(campaign, offers_stream))
        k_google = _tracker_stream(campaign, google_stream)
        new_geo = list(k_google.filters_geo) if k_google and k_google.filters_geo else None
        if new_geo is not None:
            await self._validator.known_geo_codes(new_geo)
            await self._guard.end_read()

        traffic = (
            TrafficStatus.active if campaign.state == "active" else TrafficStatus.disabled
        )
        reserved = {
            s.keitaro_stream_id
            for s in (google_stream, offers_stream)
            if s is not None and s.keitaro_stream_id is not None
        }
        known = {s.keitaro_stream_id for s in streams if s.keitaro_stream_id is not None}
        tracker_ids = {ks.stream_id for ks in campaign.streams}
        new_plain_ids = [
            ks.stream_id
            for ks in campaign.streams
            if ks.stream_id not in reserved and ks.stream_id not in known and not ks.offers
        ]
        gone_plain = [
            s
            for s in streams
            if s.type == StreamType.plain
            and s.keitaro_stream_id is not None
            and s.keitaro_stream_id not in tracker_ids
        ]
        offers_stream_id = offers_stream.id

        async def write() -> None:
            if new_geo is not None:
                await self._uow.companies.replace_geos(company_id, new_geo)
            await self._uow.companies.set_traffic_status(company_id, traffic)
            position = max((s.position for s in streams), default=2)
            for keitaro_stream_id in new_plain_ids:
                position += 1
                await self._uow.streams.add(
                    Stream(
                        company_id=company_id,
                        type=StreamType.plain,
                        keitaro_stream_id=keitaro_stream_id,
                        position=position,
                    )
                )
            for s in gone_plain:
                await self._uow.streams.delete(s)
            await self._uow.streams.replace_offers(
                offers_stream_id, to_rows(offers_stream_id, weights)
            )

        await self._guard.persist_after_tracker(company_id, token, write)
        return await self._queries.get_company(company_id)

    @staticmethod
    def _merge_offers(local_stream: Stream, tracker: KeitaroStream | None) -> list[OfferWeight]:
        """Tracker shares win as-is (no normalize); local rows missing in tracker are archived."""
        tracker_offers = {o.offer_id: int(o.share) for o in (tracker.offers if tracker else [])}
        weights: list[OfferWeight] = []
        local_ids: set[int] = set()
        for local in local_stream.offers:
            local_ids.add(local.offer_id)
            share = tracker_offers.get(local.offer_id)
            if share is None:
                weights.append(
                    OfferWeight(
                        offer_id=local.offer_id,
                        percent=int(local.percent),
                        pinned=bool(local.pinned),
                        removed=True,
                        position=int(local.position),
                    )
                )
                continue
            weights.append(
                OfferWeight(
                    offer_id=local.offer_id,
                    percent=share,
                    pinned=bool(local.pinned)
                    and not local.removed
                    and int(local.percent) == share,
                    removed=False,
                    position=int(local.position),
                )
            )
        position = max((o.position for o in local_stream.offers), default=0)
        for offer_id, share in tracker_offers.items():
            if offer_id in local_ids:
                continue
            position += 1
            weights.append(
                OfferWeight(
                    offer_id=offer_id, percent=share, pinned=False, removed=False, position=position
                )
            )
        return weights


def _tracker_stream(campaign: KeitaroCampaign, local: Stream | None) -> KeitaroStream | None:
    if local is None or not local.keitaro_stream_id:
        return None
    return next((s for s in campaign.streams if s.stream_id == local.keitaro_stream_id), None)
