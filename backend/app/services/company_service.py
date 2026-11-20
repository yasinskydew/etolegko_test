from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.keitaro import CreatedCampaign, KeitaroClient
from app.db.errors import COMPANY_NAME_UNIQUE, constraint_name
from app.errors import AppError
from app.models import (
    Company,
    CompanyGeo,
    CompanyLifecycle,
    IdempotencyKey,
    Stream,
    StreamOffer,
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
    CompanyApplyRequest,
    CompanyListResponse,
    CompanyOut,
    CreateCompanyRequest,
    DriftOut,
    StatsOut,
)
from app.services import weight_util
from app.services.company_mapper import (
    build_name_cache,
    compute_drift,
    map_company,
    map_company_list_item,
)
from app.services.weight_util import OfferWeight, WeightError

logger = logging.getLogger(__name__)

NAME_PREFIX = "test_yasinsky_company"
NAME_RE = re.compile(r"^[a-zA-Z0-9_\- ]{1,64}$")
GEO_RE = re.compile(r"^[A-Z]{2}$")
# Longer than one create (Keitaro timeout x retries x calls); older `creating` rows are crashed.
CREATING_TTL = timedelta(minutes=5)


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
        # No Keitaro reconcile on list (no mass Sync/drift updates).
        # Drift is computed on company card GET only.
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
        await self._end_read()

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

        await self._companies.fail_stale_creating(CREATING_TTL)
        await self._session.commit()

        existing_key = await self._idempotency.get(idempotency_key)
        if existing_key is not None:
            replay = await self._replay_or_retry(existing_key, payload_hash)
            if replay is not None:
                return replay, 200

        duplicate = await self._companies.get_by_name_lower(body.name)
        if duplicate is not None:
            if duplicate.lifecycle != CompanyLifecycle.failed:
                raise AppError(
                    409,
                    "name_taken",
                    f"This name is already used ({duplicate.lifecycle.value}).",
                    fields={"name": "Already exists. Pick another name."},
                )
            await self._purge_failed(duplicate)
        await self._end_read()

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

        company_id = await self._reserve(body, idempotency_key, payload_hash)
        if company_id is None:
            return await self._replay_after_race(idempotency_key, payload_hash), 200

        google_url = os.environ.get("GOOGLE_URL", "https://google.com")
        try:
            created = await self._keitaro.create_company_campaign(
                name=body.name,
                geo_codes=body.geo_codes,
                offer_id=body.offer_id,
                google_url=google_url,
            )
        except Exception as exc:
            await self._discard_reserved(company_id)
            if isinstance(exc, AppError):
                raise
            raise AppError(
                502, "keitaro_bad_gateway", "Keitaro create failed."
            ) from exc

        try:
            await self._finalize(company_id, created, body.offer_id)
        except Exception:
            logger.exception("Failed to finalize company %s after Keitaro create", company_id)
            await self._session.rollback()
            await self._compensate_finalize(company_id, created.campaign_id)
            raise AppError(
                502,
                "keitaro_bad_gateway",
                "Company could not be finalized after tracker create. Retry the request.",
            )

        company = await self._companies.get_with_details(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        await self._end_read()
        name_cache = await build_name_cache(self._keitaro, company)
        return map_company(company, name_cache=name_cache, drift=DriftOut()), 201

    async def apply(self, company_id: int, body: CompanyApplyRequest) -> CompanyOut:
        """Apply full draft to Keitaro, then persist exactly what the tracker accepted."""
        company = await self._load_ready(company_id)
        token = company.updated_at
        campaign_id = self._campaign_id(company)

        geo_codes = await self._validate_geo_codes(body.geo_codes)
        stream = await self._streams.get_offers_stream(company_id)
        if stream is None or stream.keitaro_stream_id is None:
            raise AppError(404, "not_found", "Offers stream not found.")
        google = await self._streams.get_google_stream(company_id)
        if google is None or google.keitaro_stream_id is None:
            raise AppError(404, "not_found", "Google stream not found.")

        weights = [
            OfferWeight(
                offer_id=o.offer_id,
                percent=int(o.percent),
                pinned=bool(o.pinned),
                removed=bool(o.removed),
                position=int(o.position),
            )
            for o in body.offers
        ]
        try:
            weights = weight_util.redistribute(weights)
        except WeightError as exc:
            raise AppError(422, "validation_error", str(exc)) from exc

        pinned_sum = sum(w.percent for w in weights if not w.removed and w.pinned)
        if pinned_sum > 100:
            raise AppError(422, "validation_error", "Pinned sum exceeds 100")

        participants = [
            (w.offer_id, int(w.percent))
            for w in sorted(weights, key=lambda x: x.position)
            if not w.removed
        ]
        offers_stream_id = stream.id
        await self._end_read()

        geo_applied = False
        try:
            await self._keitaro.update_google_geo(
                campaign_id=campaign_id,
                stream_id=google.keitaro_stream_id,
                geo_codes=geo_codes,
            )
            geo_applied = True
            await self._keitaro.update_stream_offers(
                campaign_id=campaign_id,
                stream_id=stream.keitaro_stream_id,
                offers=participants,
            )
        except AppError as exc:
            if not geo_applied:
                raise
            await self._persist_after_tracker(
                company_id, token, lambda: self._companies.replace_geos(company_id, geo_codes)
            )
            raise AppError(
                502,
                "keitaro_partial_apply",
                "Geo was applied in Keitaro, offers were not. "
                "Saved geo only; retry Push to apply offers.",
                fields={"geo_codes": "Applied.", "offers": f"Not applied: {exc.message}"},
            ) from exc

        async def write() -> None:
            await self._streams.replace_offers(
                offers_stream_id,
                [
                    StreamOffer(
                        stream_id=offers_stream_id,
                        offer_id=w.offer_id,
                        percent=w.percent,
                        pinned=w.pinned,
                        removed=w.removed,
                        position=w.position,
                    )
                    for w in weights
                ],
            )
            await self._companies.replace_geos(company_id, geo_codes)

        await self._persist_after_tracker(company_id, token, write)
        return await self.get_company(company_id)

    async def fetch(self, company_id: int) -> CompanyOut:
        company = await self._load_ready(company_id)
        token = company.updated_at
        campaign_id = self._campaign_id(company)

        streams = await self._streams.list_by_company(company_id)
        offers_stream = next((s for s in streams if s.type == StreamType.offers), None)
        google_stream = next((s for s in streams if s.type == StreamType.google), None)
        if offers_stream is None:
            raise AppError(404, "not_found", "Offers stream not found.")
        await self._end_read()

        campaign = await self._keitaro.get_campaign(campaign_id)
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
        new_geo: list[str] | None = None
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
            new_geo = list(k_google.filters_geo)
        await self._end_read()

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

        async def write() -> None:
            if new_geo is not None:
                await self._companies.replace_geos(company_id, new_geo)
            await self._companies.set_traffic_status(company_id, traffic)
            max_pos = max((s.position for s in streams), default=2)
            for keitaro_stream_id in new_plain_ids:
                max_pos += 1
                await self._streams.add(
                    Stream(
                        company_id=company_id,
                        type=StreamType.plain,
                        keitaro_stream_id=keitaro_stream_id,
                        position=max_pos,
                    )
                )
            for s in gone_plain:
                await self._streams.delete(s)
            await self._streams.replace_offers(offers_stream.id, new_rows)

        await self._persist_after_tracker(company_id, token, write)
        return await self.get_company(company_id)

    async def set_traffic(
        self,
        company_id: int,
        *,
        enable: bool,
    ) -> CompanyOut:
        company = await self._load_ready(company_id, require_campaign=False)
        target = TrafficStatus.active if enable else TrafficStatus.disabled
        if company.traffic_status == target:
            return await self.get_company(company_id)
        campaign_id = company.keitaro_campaign_id
        if campaign_id is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")
        token = company.updated_at
        await self._end_read()

        if enable:
            await self._keitaro.enable_campaign(campaign_id)
        else:
            await self._keitaro.disable_campaign(campaign_id)

        await self._persist_after_tracker(
            company_id,
            token,
            lambda: self._companies.set_traffic_status(company_id, target),
        )
        return await self.get_company(company_id)

    async def stats(self, company_id: int) -> StatsOut:
        company = await self._companies.get_by_id(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        campaign_id = company.keitaro_campaign_id
        await self._end_read()
        if campaign_id is None:
            return StatsOut()
        stats = await self._keitaro.get_stats(campaign_id)
        return StatsOut(clicks=stats.clicks, uniques=stats.uniques, bots=stats.bots)

    async def _end_read(self) -> None:
        """End the read transaction so no connection/row lock is held across tracker HTTP."""
        await self._session.commit()

    async def _load_ready(self, company_id: int, *, require_campaign: bool = True) -> Company:
        company = await self._companies.get_by_id(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.lifecycle != CompanyLifecycle.ready:
            raise AppError(
                409, "validation_error", f"Company is {company.lifecycle.value}."
            )
        if require_campaign and company.keitaro_campaign_id is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")
        return company

    @staticmethod
    def _campaign_id(company: Company) -> int:
        if company.keitaro_campaign_id is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")
        return company.keitaro_campaign_id

    async def _persist_after_tracker(
        self,
        company_id: int,
        token: datetime,
        write: Callable[[], Awaitable[None]],
    ) -> None:
        """Short write transaction guarded by the `updated_at` token read before the tracker call."""
        if not await self._companies.touch_if_unchanged(company_id, token):
            await self._session.rollback()
            raise AppError(
                409,
                "concurrent_update",
                "Company was changed by another request while Keitaro was updated. "
                "Reload the card; tracker differences are shown as drift.",
            )
        await write()
        await self._session.commit()

    async def _reserve(
        self, body: CreateCompanyRequest, idempotency_key: str, payload_hash: str
    ) -> int | None:
        """Insert `creating` company + key. Returns None when a concurrent request won the key."""
        company = Company(
            name=body.name,
            lifecycle=CompanyLifecycle.creating,
            traffic_status=TrafficStatus.active,
        )
        try:
            await self._companies.add(company)
            for position, code in enumerate(body.geo_codes, start=1):
                self._session.add(
                    CompanyGeo(company_id=company.id, geo_code=code, position=position)
                )
            await self._streams.add(
                Stream(company_id=company.id, type=StreamType.google, position=1)
            )
            await self._streams.add(
                Stream(company_id=company.id, type=StreamType.offers, position=2)
            )
            await self._idempotency.add(
                IdempotencyKey(
                    key=idempotency_key,
                    payload_hash=payload_hash,
                    company_id=company.id,
                )
            )
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            if await self._idempotency.get(idempotency_key) is not None:
                return None
            if constraint_name(exc) == COMPANY_NAME_UNIQUE:
                raise AppError(
                    409,
                    "name_taken",
                    "This name is already used.",
                    fields={"name": "Already exists. Pick another name."},
                ) from exc
            raise
        return company.id

    async def _replay_after_race(self, idempotency_key: str, payload_hash: str) -> CompanyOut:
        key = await self._idempotency.get(idempotency_key)
        if key is None:
            raise AppError(409, "idempotency_conflict", "Idempotency-Key race; retry.")
        replay = await self._replay_or_retry(key, payload_hash, allow_retry=False)
        if replay is None:
            raise AppError(409, "idempotency_conflict", "Idempotency-Key race; retry.")
        return replay

    async def _replay_or_retry(
        self,
        key: IdempotencyKey,
        payload_hash: str,
        *,
        allow_retry: bool = True,
    ) -> CompanyOut | None:
        """Replay for the same payload; None when a failed create was purged and must be redone."""
        if key.payload_hash != payload_hash:
            raise AppError(
                409,
                "idempotency_conflict",
                "Idempotency-Key was used with a different payload.",
            )
        company = await self._companies.get_with_details(key.company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.lifecycle == CompanyLifecycle.failed and allow_retry:
            await self._purge_failed(company)
            return None
        await self._end_read()
        name_cache = await build_name_cache(self._keitaro, company)
        return map_company(company, name_cache=name_cache, drift=DriftOut())

    async def _purge_failed(self, company: Company) -> None:
        """Remove a `failed` company (and its orphan tracker campaign) so create can be retried."""
        company_id = company.id
        campaign_id = company.keitaro_campaign_id
        await self._end_read()
        if campaign_id is not None:
            await self._keitaro.delete_campaign(campaign_id)
        await self._delete_company(company_id)

    async def _discard_reserved(self, company_id: int) -> None:
        try:
            await self._session.rollback()
            await self._delete_company(company_id)
        except Exception:
            logger.exception("Failed to discard reserved company %s", company_id)

    async def _finalize(self, company_id: int, created: CreatedCampaign, offer_id: int) -> None:
        company = await self._companies.get_by_id_for_update(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        google_stream = await self._streams.get_google_stream(company_id)
        offers_stream = await self._streams.get_offers_stream(company_id)
        if google_stream is None or offers_stream is None:
            raise AppError(500, "internal_error", "Reserved streams are missing.")
        company.keitaro_campaign_id = created.campaign_id
        company.lifecycle = CompanyLifecycle.ready
        google_stream.keitaro_stream_id = created.google_stream_id
        offers_stream.keitaro_stream_id = created.offers_stream_id
        await self._streams.replace_offers(
            offers_stream.id,
            [
                StreamOffer(
                    stream_id=offers_stream.id,
                    offer_id=offer_id,
                    percent=100,
                    pinned=False,
                    removed=False,
                    position=1,
                )
            ],
        )
        await self._session.commit()

    async def _compensate_finalize(self, company_id: int, campaign_id: int) -> None:
        """Delete the tracker campaign; if that fails, keep an honest `failed` row for retry."""
        try:
            await self._keitaro.delete_campaign(campaign_id)
        except Exception:
            logger.exception("Compensation failed for company %s", company_id)
            try:
                await self._companies.mark_failed(company_id, campaign_id)
                await self._session.commit()
            except Exception:
                logger.exception("Could not mark company %s failed", company_id)
            return
        await self._discard_reserved(company_id)

    async def _delete_company(self, company_id: int) -> None:
        await self._idempotency.delete_for_company(company_id)
        company = await self._companies.get_by_id(company_id)
        if company is not None:
            await self._companies.delete(company)
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
