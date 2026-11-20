from __future__ import annotations

import hashlib
import json
import logging
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from app.clients.keitaro import CreatedCampaign, KeitaroClient
from app.db.errors import COMPANY_NAME_UNIQUE, constraint_name
from app.errors import AppError
from app.models import (
    Company,
    CompanyLifecycle,
    IdempotencyKey,
    Stream,
    StreamType,
    TrafficStatus,
)
from app.repositories import UnitOfWork
from app.schemas.company import CompanyOut, CreateCompanyRequest
from app.services.companies.guard import CompanyWriteGuard
from app.services.companies.queries import CompanyQueryService
from app.services.companies.validator import CompanyValidator
from app.services.company_mapper import to_rows
from app.services.weight_util import OfferWeight

logger = logging.getLogger(__name__)

# Longer than one create (Keitaro timeout x retries x calls); older `creating` rows are crashed.
CREATING_TTL = timedelta(minutes=5)

NAME_TAKEN_FIELDS = {"name": "Already exists. Pick another name."}


class CreateCompanyUseCase:
    """Idempotent create: reserve row, create Keitaro campaign, finalize or fail honestly."""

    def __init__(
        self,
        uow: UnitOfWork,
        keitaro: KeitaroClient,
        validator: CompanyValidator,
        guard: CompanyWriteGuard,
        queries: CompanyQueryService,
        google_url: str,
    ) -> None:
        self._uow = uow
        self._keitaro = keitaro
        self._validator = validator
        self._guard = guard
        self._queries = queries
        self._google_url = google_url

    async def execute(
        self, body: CreateCompanyRequest, idempotency_key: str
    ) -> tuple[CompanyOut, int]:
        if not idempotency_key:
            raise AppError(422, "validation_error", "Idempotency-Key header is required.")
        self._validator.name(body.name)
        body.geo_codes = await self._validator.geo_codes(body.geo_codes)
        self._validator.offer_id(body.offer_id)
        payload_hash = _payload_hash(body)

        await self._uow.companies.fail_stale_creating(CREATING_TTL)
        await self._uow.commit()

        existing_key = await self._uow.idempotency.get(idempotency_key)
        if existing_key is not None:
            replay = await self._replay_or_retry(existing_key, payload_hash)
            if replay is not None:
                return replay, 200

        duplicate = await self._uow.companies.get_by_name_lower(body.name)
        if duplicate is not None:
            if duplicate.lifecycle != CompanyLifecycle.failed:
                raise AppError(
                    409,
                    "name_taken",
                    f"This name is already used ({duplicate.lifecycle.value}).",
                    fields=NAME_TAKEN_FIELDS,
                )
            await self._purge_failed(duplicate)
        await self._guard.end_read()

        offer = await self._keitaro.get_offer(body.offer_id)
        if offer is None and not self._keitaro.noop:
            raise AppError(422, "validation_error", "offer_id not found in catalog.")
        try:
            existing_campaign = await self._keitaro.find_campaign_by_name(body.name)
        except AppError:
            existing_campaign = None
        if existing_campaign is not None:
            raise AppError(
                409,
                "name_taken",
                "This name is already used in Keitaro.",
                fields=NAME_TAKEN_FIELDS,
            )

        company_id = await self._reserve(body, idempotency_key, payload_hash)
        if company_id is None:
            return await self._replay_after_race(idempotency_key, payload_hash), 200

        try:
            created = await self._keitaro.create_company_campaign(
                name=body.name,
                geo_codes=body.geo_codes,
                offer_id=body.offer_id,
                google_url=self._google_url,
            )
        except Exception as exc:
            await self._discard_reserved(company_id)
            if isinstance(exc, AppError):
                raise
            raise AppError(502, "keitaro_bad_gateway", "Keitaro create failed.") from exc

        try:
            await self._finalize(company_id, created, body.offer_id)
        except Exception:
            logger.exception("Failed to finalize company %s after Keitaro create", company_id)
            await self._uow.rollback()
            await self._compensate_finalize(company_id, created.campaign_id)
            raise AppError(
                502,
                "keitaro_bad_gateway",
                "Company could not be finalized after tracker create. Retry the request.",
            )

        return await self._queries.get_without_drift(company_id), 201

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
            await self._uow.companies.add(company)
            await self._uow.companies.replace_geos(company.id, body.geo_codes)
            await self._uow.streams.add(
                Stream(company_id=company.id, type=StreamType.google, position=1)
            )
            await self._uow.streams.add(
                Stream(company_id=company.id, type=StreamType.offers, position=2)
            )
            await self._uow.idempotency.add(
                IdempotencyKey(
                    key=idempotency_key, payload_hash=payload_hash, company_id=company.id
                )
            )
            await self._uow.commit()
        except IntegrityError as exc:
            await self._uow.rollback()
            if await self._uow.idempotency.get(idempotency_key) is not None:
                return None
            if constraint_name(exc) == COMPANY_NAME_UNIQUE:
                raise AppError(
                    409, "name_taken", "This name is already used.", fields=NAME_TAKEN_FIELDS
                ) from exc
            raise
        return company.id

    async def _replay_after_race(self, idempotency_key: str, payload_hash: str) -> CompanyOut:
        key = await self._uow.idempotency.get(idempotency_key)
        replay = (
            await self._replay_or_retry(key, payload_hash, allow_retry=False)
            if key is not None
            else None
        )
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
        company = await self._uow.companies.get_by_id(key.company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.lifecycle == CompanyLifecycle.failed and allow_retry:
            await self._purge_failed(company)
            return None
        return await self._queries.get_without_drift(company.id)

    async def _purge_failed(self, company: Company) -> None:
        """Remove a `failed` company (and its orphan tracker campaign) so create can be retried."""
        company_id = company.id
        campaign_id = company.keitaro_campaign_id
        await self._guard.end_read()
        if campaign_id is not None:
            await self._keitaro.delete_campaign(campaign_id)
        await self._delete_company(company_id)

    async def _discard_reserved(self, company_id: int) -> None:
        try:
            await self._uow.rollback()
            await self._delete_company(company_id)
        except Exception:
            logger.exception("Failed to discard reserved company %s", company_id)

    async def _finalize(self, company_id: int, created: CreatedCampaign, offer_id: int) -> None:
        company = await self._uow.companies.get_by_id_for_update(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        google_stream = await self._uow.streams.get_google_stream(company_id)
        offers_stream = await self._uow.streams.get_offers_stream(company_id)
        if google_stream is None or offers_stream is None:
            raise AppError(500, "internal_error", "Reserved streams are missing.")
        company.keitaro_campaign_id = created.campaign_id
        company.lifecycle = CompanyLifecycle.ready
        google_stream.keitaro_stream_id = created.google_stream_id
        offers_stream.keitaro_stream_id = created.offers_stream_id
        initial = OfferWeight(offer_id=offer_id, percent=100, pinned=False, removed=False, position=1)
        await self._uow.streams.replace_offers(
            offers_stream.id, to_rows(offers_stream.id, [initial])
        )
        await self._uow.commit()

    async def _compensate_finalize(self, company_id: int, campaign_id: int) -> None:
        """Delete the tracker campaign; if that fails, keep an honest `failed` row for retry."""
        try:
            await self._keitaro.delete_campaign(campaign_id)
        except Exception:
            logger.exception("Compensation failed for company %s", company_id)
            try:
                await self._uow.companies.mark_failed(company_id, campaign_id)
                await self._uow.commit()
            except Exception:
                logger.exception("Could not mark company %s failed", company_id)
            return
        await self._discard_reserved(company_id)

    async def _delete_company(self, company_id: int) -> None:
        await self._uow.idempotency.delete_for_company(company_id)
        company = await self._uow.companies.get_by_id(company_id)
        if company is not None:
            await self._uow.companies.delete(company)
        await self._uow.commit()


def _payload_hash(body: CreateCompanyRequest) -> str:
    raw = json.dumps(
        {"name": body.name, "geo_codes": body.geo_codes, "offer_id": body.offer_id},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
