from __future__ import annotations

from app.clients.keitaro import KeitaroClient
from app.errors import AppError
from app.models import Company, CompanyLifecycle
from app.repositories import UnitOfWork
from app.schemas.company import CompanyListResponse, CompanyOut, DriftOut, StatsOut
from app.services.companies.guard import CompanyWriteGuard
from app.services.company_mapper import (
    build_name_cache,
    compute_drift,
    map_company,
    map_company_list_item,
)


class CompanyQueryService:
    def __init__(
        self, uow: UnitOfWork, keitaro: KeitaroClient, guard: CompanyWriteGuard
    ) -> None:
        self._uow = uow
        self._keitaro = keitaro
        self._guard = guard

    async def list_companies(
        self, *, q: str | None, page: int, page_size: int
    ) -> CompanyListResponse:
        items, total = await self._uow.companies.list_paginated(
            q=q, page=page, page_size=page_size
        )
        return CompanyListResponse(
            items=[map_company_list_item(c) for c in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def get_company(self, company_id: int) -> CompanyOut:
        company = await self._load_details(company_id)
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
        return map_company(
            company,
            name_cache=name_cache,
            drift=drift,
            reconcile_unavailable=reconcile_unavailable,
        )

    async def get_without_drift(self, company_id: int) -> CompanyOut:
        """Card right after create/replay: tracker state was just written, skip reconcile."""
        company = await self._load_details(company_id)
        name_cache = await build_name_cache(self._keitaro, company)
        return map_company(company, name_cache=name_cache, drift=DriftOut())

    async def stats(self, company_id: int) -> StatsOut:
        company = await self._uow.companies.get_by_id(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        campaign_id = company.keitaro_campaign_id
        await self._guard.end_read()
        if campaign_id is None:
            return StatsOut()
        stats = await self._keitaro.get_stats(campaign_id)
        return StatsOut(clicks=stats.clicks, uniques=stats.uniques, bots=stats.bots)

    async def _load_details(self, company_id: int) -> Company:
        company = await self._uow.companies.get_with_details(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        await self._guard.end_read()
        return company
