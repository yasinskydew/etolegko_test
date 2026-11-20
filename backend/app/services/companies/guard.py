from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from app.errors import AppError
from app.models import Company, CompanyLifecycle
from app.repositories import UnitOfWork


class CompanyWriteGuard:
    """Shared rules for tracker writes: ready check, no transaction across HTTP, CAS on write."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def end_read(self) -> None:
        """End the read transaction so no connection/row lock is held across tracker HTTP."""
        await self._uow.commit()

    async def load_ready(self, company_id: int) -> Company:
        company = await self._uow.companies.get_by_id(company_id)
        if company is None:
            raise AppError(404, "not_found", "Company not found.")
        if company.lifecycle != CompanyLifecycle.ready:
            raise AppError(
                409, "company_not_ready", f"Company is {company.lifecycle.value}."
            )
        return company

    @staticmethod
    def campaign_id(company: Company) -> int:
        if company.keitaro_campaign_id is None:
            raise AppError(409, "campaign_missing", "Campaign missing in tracker.")
        return company.keitaro_campaign_id

    async def persist_after_tracker(
        self,
        company_id: int,
        token: datetime,
        write: Callable[[], Awaitable[None]],
    ) -> None:
        """Short write transaction guarded by the `updated_at` token read before the tracker call."""
        if not await self._uow.companies.touch_if_unchanged(company_id, token):
            await self._uow.rollback()
            raise AppError(
                409,
                "concurrent_update",
                "Company was changed by another request while Keitaro was updated. "
                "Reload the card; tracker differences are shown as drift.",
            )
        await write()
        await self._uow.commit()
