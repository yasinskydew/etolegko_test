from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.keitaro import KeitaroClient
from app.errors import AppError
from app.models import (
    Company,
    CompanyGeo,
    CompanyLifecycle,
    IdempotencyKey,
    Stream,
    StreamOffer,
    StreamOfferSnapshot,
    StreamType,
    TrafficStatus,
)
from app.repositories import (
    CompanyRepository,
    GeoRepository,
    IdempotencyKeyRepository,
    StreamRepository,
)
from app.schemas.company import (
    CompanyListResponse,
    CompanyOut,
    CreateCompanyRequest,
    DriftOut,
    GeoPatchRequest,
    StatsOut,
    StreamActionRequest,
    VersionBody,
)
from app.services import weight_util
from app.services.company_mapper import (
    build_name_cache,
    compute_drift,
    map_company,
    map_company_list_item,
)
from app.services.sync_status import compute_stream_sync
from app.services.weight_util import OfferWeight, WeightError

logger = logging.getLogger(__name__)

NAME_PREFIX = "test_yasinsky_company"
NAME_RE = re.compile(r"^[a-zA-Z0-9_\- ]{1,64}$")
GEO_RE = re.compile(r"^[A-Z]{2}$")


class CompanyService:
    def __init__(
        self,
        session: AsyncSession,
        company_repo: CompanyRepository,
        stream_repo: StreamRepository,
        geo_repo: GeoRepository,
        idempotency_repo: IdempotencyKeyRepository,
        keitaro: KeitaroClient,
    ) -> None:
        self._session = session
        self._companies = company_repo
        self._streams = stream_repo
        self._geos = geo_repo
        self._idempotency = idempotency_repo
        self._keitaro = keitaro

    async def list_companies(
        self,
        *,
        q: str | None,
        page: int,
        page_size: int,
    ) -> CompanyListResponse:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        items, total = await self._companies.list_paginated(
            q=q, page=page, page_size=page_size
        )
        return CompanyListResponse(
            items=[map_company_list_item(c) for c in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def get_company(self, company_id: int) -> CompanyOut:
        company = await self._companies.get_with_details(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.lifecycle == CompanyLifecycle.creating:
            # card allowed; editor blocked separately by callers that need ready
            pass

        name_cache = await build_name_cache(self._keitaro, company)
        drift: DriftOut | None = None
        reconcile_unavailable = False
        if (
            company.lifecycle == CompanyLifecycle.ready
            and company.keitaro_campaign_id is not None
        ):
            try:
                campaign = await self._keitaro.get_campaign(company.keitaro_campaign_id)
                drift = compute_drift(company, campaign)
            except AppError:
                reconcile_unavailable = True
                drift = None
        return map_company(
            company,
            name_cache=name_cache,
            drift=drift,
            reconcile_unavailable=reconcile_unavailable,
        )

    async def create_company(
        self,
        body: CreateCompanyRequest,
        idempotency_key: str,
    ) -> tuple[CompanyOut, int]:
        if not idempotency_key:
            raise AppError(
                422, "validation_error", "Idempotency-Key header is required."
            )
        self._validate_name(body.name)
        body.geo_codes = await self._validate_geo_codes(body.geo_codes)
        self._validate_offer_id(body.offer_id)

        payload_hash = self._payload_hash(body)
        existing_key = await self._idempotency.get(idempotency_key)
        if existing_key is not None:
            if existing_key.payload_hash != payload_hash:
                raise AppError(
                    409,
                    "idempotency_conflict",
                    "Idempotency-Key was used with a different payload.",
                )
            company = await self._companies.get_with_details(existing_key.company_id)
            if company is None:
                raise AppError(404, "not_found", "Company not found.")
            name_cache = await build_name_cache(self._keitaro, company)
            return map_company(company, name_cache=name_cache, drift=DriftOut()), 200

        duplicate = await self._companies.get_by_name_lower(body.name)
        if duplicate is not None:
            raise AppError(
                409,
                "name_taken",
                f"This name is already used ({duplicate.lifecycle.value}).",
                fields={"name": "Already exists. Pick another name."},
            )

        offer = await self._keitaro.get_offer(body.offer_id)
        if offer is None and not self._keitaro.noop:
            raise AppError(422, "validation_error", "offer_id not found in catalog.")

        try:
            existing_k = await self._keitaro.find_campaign_by_name(body.name)
        except AppError:
            existing_k = None
        if existing_k is not None:
            raise AppError(
                409,
                "name_taken",
                "This name is already used in Keitaro.",
                fields={"name": "Already exists. Pick another name."},
            )

        company = Company(
            name=body.name,
            lifecycle=CompanyLifecycle.creating,
            traffic_status=TrafficStatus.active,
            version=1,
        )
        try:
            await self._companies.add(company)
            for position, code in enumerate(body.geo_codes, start=1):
                self._session.add(
                    CompanyGeo(
                        company_id=company.id,
                        geo_code=code,
                        position=position,
                    )
                )
            google_stream = Stream(
                company_id=company.id,
                type=StreamType.google,
                position=1,
            )
            offers_stream = Stream(
                company_id=company.id,
                type=StreamType.offers,
                position=2,
            )
            await self._streams.add(google_stream)
            await self._streams.add(offers_stream)
            self._session.add(
                IdempotencyKey(
                    key=idempotency_key,
                    payload_hash=payload_hash,
                    company_id=company.id,
                )
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise AppError(
                409,
                "name_taken",
                "This name is already used.",
                fields={"name": "Already exists. Pick another name."},
            ) from exc

        google_url = os.environ.get("GOOGLE_URL", "https://google.com")
        created = None
        try:
            created = await self._keitaro.create_company_campaign(
                name=body.name,
                geo_codes=body.geo_codes,
                offer_id=body.offer_id,
                google_url=google_url,
            )
        except AppError as exc:
            await self._compensate_create(company.id, None)
            raise exc
        except Exception as exc:
            await self._compensate_create(company.id, None)
            raise AppError(
                502, "keitaro_bad_gateway", "Keitaro create failed."
            ) from exc

        company_id = company.id
        try:
            company = await self._companies.get_by_id_for_update(company_id)
            if company is None:
                raise AppError(404, "not_found", "Company not found.")
            company.keitaro_campaign_id = created.campaign_id
            company.lifecycle = CompanyLifecycle.ready
            company.updated_at = datetime.now(UTC)
            google_stream = await self._streams.get_google_stream(company_id)
            offers_stream = await self._streams.get_offers_stream(company_id)
            assert google_stream is not None and offers_stream is not None
            google_stream.keitaro_stream_id = created.google_stream_id
            offers_stream.keitaro_stream_id = created.offers_stream_id
            offer_row = StreamOffer(
                stream_id=offers_stream.id,
                offer_id=body.offer_id,
                percent=100,
                pinned=False,
                removed=False,
                position=1,
            )
            snap = StreamOfferSnapshot(
                stream_id=offers_stream.id,
                offer_id=body.offer_id,
                percent=100,
                pinned=False,
                removed=False,
                position=1,
            )
            self._session.add(offer_row)
            self._session.add(snap)
            await self._session.commit()
        except Exception:
            logger.exception("Failed to finalize company %s after Keitaro create", company_id)
            await self._session.rollback()
            try:
                await self._keitaro.delete_campaign(created.campaign_id)
                await self._compensate_create(company_id, None)
            except Exception:
                logger.exception("Compensation failed for company %s", company_id)
            raise AppError(
                502,
                "keitaro_bad_gateway",
                "Company left in creating state after tracker error.",
            )

        company = await self._companies.get_with_details(company_id)
        assert company is not None
        name_cache = await build_name_cache(self._keitaro, company)
        return map_company(company, name_cache=name_cache, drift=DriftOut()), 201

    async def apply_action(
        self,
        company_id: int,
        stream_id: int,
        body: StreamActionRequest,
    ) -> CompanyOut:
        company = await self._companies.get_by_id_for_update(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.lifecycle != CompanyLifecycle.ready:
            raise AppError(
                409,
                "validation_error",
                "Company is still creating.",
            )
        if company.version != body.expected_version:
            raise AppError(409, "version_conflict", "expected_version mismatch.")

        stream = await self._streams.get_by_id(stream_id)
        if stream is None or stream.company_id != company_id:
            raise AppError(404, "not_found", "Stream not found.")
        if stream.type != StreamType.offers:
            raise AppError(422, "validation_error", "Actions only allowed on offers stream.")

        weights = [
            OfferWeight(
                offer_id=o.offer_id,
                percent=int(o.percent),
                pinned=bool(o.pinned),
                removed=bool(o.removed),
                position=int(o.position),
            )
            for o in stream.offers
        ]
        try:
            if body.action == "add":
                weights = weight_util.apply_add(weights, body.offer_id)
            elif body.action == "remove":
                weights = weight_util.apply_remove(weights, body.offer_id)
            elif body.action == "restore":
                weights = weight_util.apply_restore(weights, body.offer_id)
            elif body.action == "pin":
                weights = weight_util.apply_pin(weights, body.offer_id)
            elif body.action == "unpin":
                weights = weight_util.apply_unpin(weights, body.offer_id)
            elif body.action == "set_percent":
                if body.percent is None:
                    raise AppError(
                        422, "validation_error", "percent is required for set_percent."
                    )
                weights = weight_util.apply_set_percent(
                    weights, body.offer_id, body.percent
                )
            else:
                raise AppError(422, "validation_error", "Unknown action.")
        except WeightError as exc:
            raise AppError(422, "validation_error", str(exc)) from exc

        new_offers = [
            StreamOffer(
                stream_id=stream.id,
                offer_id=w.offer_id,
                percent=w.percent,
                pinned=w.pinned,
                removed=w.removed,
                position=w.position,
            )
            for w in weights
        ]
        await self._streams.replace_offers(stream.id, new_offers)
        company.version += 1
        company.updated_at = datetime.now(UTC)
        await self._session.commit()
        return await self.get_company(company_id)

    async def push(self, company_id: int) -> CompanyOut:
        company = await self._companies.get_by_id_for_update(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.lifecycle != CompanyLifecycle.ready:
            raise AppError(409, "validation_error", "Company is still creating.")
        if company.keitaro_campaign_id is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")

        stream = await self._streams.get_offers_stream(company_id)
        if stream is None or stream.keitaro_stream_id is None:
            raise AppError(404, "not_found", "Offers stream not found.")

        participants = [
            (o.offer_id, int(o.percent))
            for o in sorted(stream.offers, key=lambda x: x.position)
            if not o.removed
        ]
        try:
            await self._keitaro.update_stream_offers(
                campaign_id=company.keitaro_campaign_id,
                stream_id=stream.keitaro_stream_id,
                offers=participants,
            )
        except AppError:
            await self._session.rollback()
            raise

        snapshots = [
            StreamOfferSnapshot(
                stream_id=stream.id,
                offer_id=o.offer_id,
                percent=int(o.percent),
                pinned=bool(o.pinned),
                removed=bool(o.removed),
                position=int(o.position),
            )
            for o in stream.offers
        ]
        await self._streams.replace_snapshots(stream.id, snapshots)
        company.version += 1
        company.updated_at = datetime.now(UTC)
        await self._session.commit()
        return await self.get_company(company_id)

    async def cancel(self, company_id: int) -> CompanyOut:
        company = await self._companies.get_by_id_for_update(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        stream = await self._streams.get_offers_stream(company_id)
        if stream is None:
            raise AppError(404, "not_found", "Offers stream not found.")

        restored = [
            StreamOffer(
                stream_id=stream.id,
                offer_id=s.offer_id,
                percent=int(s.percent),
                pinned=bool(s.pinned),
                removed=bool(s.removed),
                position=int(s.position),
            )
            for s in stream.snapshots
        ]
        await self._streams.replace_offers(stream.id, restored)
        company.version += 1
        company.updated_at = datetime.now(UTC)
        await self._session.commit()
        return await self.get_company(company_id)

    async def fetch(self, company_id: int) -> CompanyOut:
        company = await self._companies.get_by_id_for_update(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.lifecycle != CompanyLifecycle.ready:
            raise AppError(409, "validation_error", "Company is still creating.")
        if company.keitaro_campaign_id is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")

        streams = await self._streams.list_by_company(company_id)
        offers_stream = next((s for s in streams if s.type == StreamType.offers), None)
        google_stream = next((s for s in streams if s.type == StreamType.google), None)
        if offers_stream is None:
            raise AppError(404, "not_found", "Offers stream not found.")
        if compute_stream_sync(offers_stream) != "synced":
            raise AppError(
                409, "fetch_blocked", "Fetch is blocked while stream is in update mode."
            )

        campaign = await self._keitaro.get_campaign(company.keitaro_campaign_id)
        if campaign is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")

        k_offers = None
        if offers_stream.keitaro_stream_id:
            k_offers = next(
                (
                    s
                    for s in campaign.streams
                    if s.stream_id == offers_stream.keitaro_stream_id
                ),
                None,
            )
        tracker_offers = {
            o.offer_id: int(o.share) for o in (k_offers.offers if k_offers else [])
        }

        by_id = {o.offer_id: o for o in offers_stream.offers}
        next_position = max((o.position for o in offers_stream.offers), default=0)
        new_rows: list[StreamOffer] = []

        for offer_id, local in list(by_id.items()):
            if offer_id not in tracker_offers:
                new_rows.append(
                    StreamOffer(
                        stream_id=offers_stream.id,
                        offer_id=offer_id,
                        percent=int(local.percent),
                        pinned=bool(local.pinned),
                        removed=True,
                        position=int(local.position),
                    )
                )
            else:
                share = tracker_offers[offer_id]
                pinned = bool(local.pinned) and int(local.percent) == share and not local.removed
                if local.removed:
                    pinned = False
                new_rows.append(
                    StreamOffer(
                        stream_id=offers_stream.id,
                        offer_id=offer_id,
                        percent=share,
                        pinned=pinned,
                        removed=False,
                        position=int(local.position),
                    )
                )

        for offer_id, share in tracker_offers.items():
            if offer_id in by_id:
                continue
            next_position += 1
            new_rows.append(
                StreamOffer(
                    stream_id=offers_stream.id,
                    offer_id=offer_id,
                    percent=share,
                    pinned=False,
                    removed=False,
                    position=next_position,
                )
            )

        # geo from google stream filters
        k_google = None
        if google_stream and google_stream.keitaro_stream_id:
            k_google = next(
                (
                    s
                    for s in campaign.streams
                    if s.stream_id == google_stream.keitaro_stream_id
                ),
                None,
            )
        if k_google is not None and k_google.filters_geo:
            found = await self._geos.get_by_codes(k_google.filters_geo)
            found_codes = {g.code for g in found}
            unknown = [c for c in k_google.filters_geo if c not in found_codes]
            if unknown:
                raise AppError(
                    422,
                    "unknown_geo",
                    f"Unknown geo codes from Keitaro: {', '.join(unknown)}",
                )
            await self._companies.replace_geos(company.id, k_google.filters_geo)

        company.traffic_status = (
            TrafficStatus.active
            if campaign.state == "active"
            else TrafficStatus.disabled
        )

        # plain streams sync
        known = {
            s.keitaro_stream_id: s
            for s in streams
            if s.keitaro_stream_id is not None
        }
        reserved = set()
        if google_stream and google_stream.keitaro_stream_id:
            reserved.add(google_stream.keitaro_stream_id)
        if offers_stream.keitaro_stream_id:
            reserved.add(offers_stream.keitaro_stream_id)

        for k_stream in campaign.streams:
            if k_stream.stream_id in reserved:
                continue
            if k_stream.stream_id in known:
                continue
            if k_stream.offers:
                continue
            max_pos = max((s.position for s in streams), default=2)
            plain = Stream(
                company_id=company.id,
                type=StreamType.plain,
                keitaro_stream_id=k_stream.stream_id,
                position=max_pos + 1,
            )
            await self._streams.add(plain)
            streams.append(plain)

        for s in list(streams):
            if s.type != StreamType.plain:
                continue
            if s.keitaro_stream_id is None:
                continue
            if s.keitaro_stream_id not in {ks.stream_id for ks in campaign.streams}:
                await self._streams.delete(s)

        await self._streams.replace_offers(offers_stream.id, new_rows)
        snapshots = [
            StreamOfferSnapshot(
                stream_id=offers_stream.id,
                offer_id=o.offer_id,
                percent=int(o.percent),
                pinned=bool(o.pinned),
                removed=bool(o.removed),
                position=int(o.position),
            )
            for o in new_rows
        ]
        await self._streams.replace_snapshots(offers_stream.id, snapshots)
        company.version += 1
        company.updated_at = datetime.now(UTC)
        await self._session.commit()
        return await self.get_company(company_id)

    async def patch_geo(self, company_id: int, body: GeoPatchRequest) -> CompanyOut:
        company = await self._companies.get_by_id_for_update(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.version != body.expected_version:
            raise AppError(409, "version_conflict", "expected_version mismatch.")
        if company.lifecycle != CompanyLifecycle.ready:
            raise AppError(409, "validation_error", "Company is still creating.")
        body.geo_codes = await self._validate_geo_codes(body.geo_codes)
        if company.keitaro_campaign_id is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")

        google = await self._streams.get_google_stream(company_id)
        if google is None or google.keitaro_stream_id is None:
            raise AppError(404, "not_found", "Google stream not found.")

        await self._keitaro.update_google_geo(
            campaign_id=company.keitaro_campaign_id,
            stream_id=google.keitaro_stream_id,
            geo_codes=body.geo_codes,
        )
        await self._companies.replace_geos(company.id, body.geo_codes)
        company.version += 1
        company.updated_at = datetime.now(UTC)
        await self._session.commit()
        return await self.get_company(company_id)

    async def set_traffic(
        self,
        company_id: int,
        body: VersionBody,
        *,
        enable: bool,
    ) -> CompanyOut:
        company = await self._companies.get_by_id_for_update(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.version != body.expected_version:
            raise AppError(409, "version_conflict", "expected_version mismatch.")
        if company.lifecycle != CompanyLifecycle.ready:
            raise AppError(409, "validation_error", "Company is still creating.")

        target = TrafficStatus.active if enable else TrafficStatus.disabled
        if company.traffic_status == target:
            await self._session.commit()
            return await self.get_company(company_id)

        if company.keitaro_campaign_id is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")

        if enable:
            await self._keitaro.enable_campaign(company.keitaro_campaign_id)
        else:
            await self._keitaro.disable_campaign(company.keitaro_campaign_id)

        company.traffic_status = target
        company.version += 1
        company.updated_at = datetime.now(UTC)
        await self._session.commit()
        return await self.get_company(company_id)

    async def stats(self, company_id: int) -> StatsOut:
        company = await self._companies.get_by_id(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.keitaro_campaign_id is None:
            return StatsOut()
        stats = await self._keitaro.get_stats(company.keitaro_campaign_id)
        return StatsOut(clicks=stats.clicks, uniques=stats.uniques, bots=stats.bots)

    async def _compensate_create(
        self,
        company_id: int,
        campaign_id: int | None,
    ) -> None:
        if campaign_id is not None:
            try:
                await self._keitaro.delete_campaign(campaign_id)
            except Exception:
                logger.exception("Failed to delete Keitaro campaign %s", campaign_id)
        await self._session.execute(
            delete(IdempotencyKey).where(IdempotencyKey.company_id == company_id)
        )
        company = await self._companies.get_by_id(company_id)
        if company is not None:
            await self._companies.delete(company)
            await self._session.commit()
        else:
            await self._session.commit()

    async def _validate_geo_codes(self, codes: list[str]) -> list[str]:
        if not codes:
            raise AppError(
                422,
                "validation_error",
                "geo_codes must not be empty.",
                fields={"geo_codes": "Add at least one geo code."},
            )
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in codes:
            code = raw.strip().upper()
            if not GEO_RE.fullmatch(code):
                raise AppError(
                    422,
                    "validation_error",
                    "Invalid geo code.",
                    fields={"geo_codes": "Use 2-letter codes from the geo list."},
                )
            if code in seen:
                raise AppError(
                    422,
                    "validation_error",
                    "Duplicate geo code.",
                    fields={"geo_codes": f"{code} is listed more than once."},
                )
            seen.add(code)
            normalized.append(code)
        found = await self._geos.get_by_codes(normalized)
        found_codes = {g.code for g in found}
        unknown = [c for c in normalized if c not in found_codes]
        if unknown:
            raise AppError(
                422,
                "unknown_geo",
                f"Unknown geo codes: {', '.join(unknown)}",
                fields={"geo_codes": "Unknown geo code."},
            )
        return normalized

    @staticmethod
    def _validate_offer_id(offer_id: int) -> None:
        if offer_id < 1:
            raise AppError(
                422,
                "validation_error",
                "offer_id is required.",
                fields={"offer_id": "Pick an offer."},
            )

    @staticmethod
    def _validate_name(name: str) -> None:
        if name != name.strip():
            raise AppError(
                422,
                "validation_error",
                "Name must not have leading/trailing spaces.",
                fields={"name": "Invalid name."},
            )
        if not NAME_RE.fullmatch(name) or not name.startswith(NAME_PREFIX):
            raise AppError(
                422,
                "validation_error",
                "Invalid company name.",
                fields={
                    "name": "Must start with test_yasinsky_company. 1-64 chars: letters, digits, _ - space."
                },
            )

    @staticmethod
    def _payload_hash(body: CreateCompanyRequest) -> str:
        raw = json.dumps(
            {
                "name": body.name,
                "geo_codes": body.geo_codes,
                "offer_id": body.offer_id,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
