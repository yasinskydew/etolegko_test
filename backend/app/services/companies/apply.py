from __future__ import annotations

from app.clients.keitaro import KeitaroClient
from app.errors import AppError
from app.repositories import UnitOfWork
from app.schemas.company import CompanyApplyRequest, CompanyOut
from app.services import weight_util
from app.services.companies.guard import CompanyWriteGuard
from app.services.companies.queries import CompanyQueryService
from app.services.companies.validator import CompanyValidator
from app.services.company_mapper import to_rows, to_weights
from app.services.weight_util import WeightError


class ApplyCompanyDraftUseCase:
    """Push the full FE draft to Keitaro, then persist exactly what the tracker accepted."""

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

    async def execute(self, company_id: int, body: CompanyApplyRequest) -> CompanyOut:
        company = await self._guard.load_ready(company_id)
        campaign_id = self._guard.campaign_id(company)
        token = company.updated_at

        geo_codes = await self._validator.geo_codes(body.geo_codes)
        stream = await self._uow.streams.get_offers_stream(company_id)
        if stream is None or stream.keitaro_stream_id is None:
            raise AppError(404, "not_found", "Offers stream not found.")
        google = await self._uow.streams.get_google_stream(company_id)
        if google is None or google.keitaro_stream_id is None:
            raise AppError(404, "not_found", "Google stream not found.")

        try:
            weights = weight_util.redistribute(to_weights(body.offers))
        except WeightError as exc:
            raise AppError(422, "validation_error", str(exc)) from exc
        if sum(w.percent for w in weights if not w.removed and w.pinned) > 100:
            raise AppError(422, "validation_error", "Pinned sum exceeds 100")

        participants = [
            (w.offer_id, w.percent)
            for w in sorted(weights, key=lambda x: x.position)
            if not w.removed
        ]
        offers_stream_id = stream.id
        await self._guard.end_read()

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
            await self._guard.persist_after_tracker(
                company_id,
                token,
                lambda: self._uow.companies.replace_geos(company_id, geo_codes),
            )
            raise AppError(
                502,
                "keitaro_partial_apply",
                "Geo was applied in Keitaro, offers were not. "
                "Saved geo only; retry Push to apply offers.",
                fields={"geo_codes": "Applied.", "offers": f"Not applied: {exc.message}"},
            ) from exc

        async def write() -> None:
            await self._uow.streams.replace_offers(
                offers_stream_id, to_rows(offers_stream_id, weights)
            )
            await self._uow.companies.replace_geos(company_id, geo_codes)

        await self._guard.persist_after_tracker(company_id, token, write)
        return await self._queries.get_company(company_id)
