from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Company, CompanyGeo, Stream


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, company_id: int) -> Company | None:
        result = await self._session.execute(
            select(Company).where(Company.id == company_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, company_id: int) -> Company | None:
        result = await self._session.execute(
            select(Company).where(Company.id == company_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_name_lower(self, name: str) -> Company | None:
        result = await self._session.execute(
            select(Company).where(func.lower(Company.name) == name.lower())
        )
        return result.scalar_one_or_none()

    async def get_with_details(self, company_id: int) -> Company | None:
        result = await self._session.execute(
            select(Company)
            .where(Company.id == company_id)
            .options(
                selectinload(Company.geos),
                selectinload(Company.streams).selectinload(Stream.offers),
                selectinload(Company.streams).selectinload(Stream.snapshots),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        q: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Company], int]:
        stmt = select(Company)
        count_stmt = select(func.count()).select_from(Company)
        if q:
            pattern = f"%{q.lower()}%"
            stmt = stmt.where(func.lower(Company.name).like(pattern))
            count_stmt = count_stmt.where(func.lower(Company.name).like(pattern))
        total = int((await self._session.execute(count_stmt)).scalar_one())
        result = await self._session.execute(
            stmt.order_by(Company.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(
                selectinload(Company.streams).selectinload(Stream.offers),
                selectinload(Company.streams).selectinload(Stream.snapshots),
            )
        )
        return list(result.scalars().all()), total

    async def add(self, company: Company) -> Company:
        self._session.add(company)
        await self._session.flush()
        return company

    async def delete(self, company: Company) -> None:
        await self._session.delete(company)
        await self._session.flush()

    async def replace_geos(
        self,
        company_id: int,
        geo_codes: list[str],
    ) -> None:
        existing = await self._session.execute(
            select(CompanyGeo).where(CompanyGeo.company_id == company_id)
        )
        for row in existing.scalars().all():
            await self._session.delete(row)
        await self._session.flush()
        for position, code in enumerate(geo_codes, start=1):
            self._session.add(
                CompanyGeo(company_id=company_id, geo_code=code, position=position)
            )
        await self._session.flush()
