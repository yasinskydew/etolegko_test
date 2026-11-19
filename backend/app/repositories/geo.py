from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Geo


class GeoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Geo]:
        result = await self._session.execute(select(Geo).order_by(Geo.code))
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Geo | None:
        result = await self._session.execute(select(Geo).where(Geo.code == code))
        return result.scalar_one_or_none()

    async def get_by_codes(self, codes: list[str]) -> list[Geo]:
        if not codes:
            return []
        result = await self._session.execute(select(Geo).where(Geo.code.in_(codes)))
        return list(result.scalars().all())

    async def add(self, geo: Geo) -> Geo:
        self._session.add(geo)
        await self._session.flush()
        return geo
