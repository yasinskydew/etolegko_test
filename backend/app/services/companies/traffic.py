from __future__ import annotations

from app.clients.keitaro import KeitaroClient
from app.models import TrafficStatus
from app.repositories import UnitOfWork
from app.schemas.company import CompanyOut
from app.services.companies.guard import CompanyWriteGuard
from app.services.companies.queries import CompanyQueryService


class TrafficService:
    def __init__(
        self,
        uow: UnitOfWork,
        keitaro: KeitaroClient,
        guard: CompanyWriteGuard,
        queries: CompanyQueryService,
    ) -> None:
        self._uow = uow
        self._keitaro = keitaro
        self._guard = guard
        self._queries = queries

    async def set_traffic(self, company_id: int, *, enable: bool) -> CompanyOut:
        company = await self._guard.load_ready(company_id)
        target = TrafficStatus.active if enable else TrafficStatus.disabled
        if company.traffic_status == target:
            return await self._queries.get_company(company_id)
        campaign_id = self._guard.campaign_id(company)
        token = company.updated_at
        await self._guard.end_read()

        if enable:
            await self._keitaro.enable_campaign(campaign_id)
        else:
            await self._keitaro.disable_campaign(campaign_id)

        await self._guard.persist_after_tracker(
            company_id,
            token,
            lambda: self._uow.companies.set_traffic_status(company_id, target),
        )
        return await self._queries.get_company(company_id)
