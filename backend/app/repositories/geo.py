from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Geo


class GeoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_codes(self, codes: list[str]) -> list[Geo]:
        if not codes:
            return []
        result = await self._session.execute(select(Geo).where(Geo.code.in_(codes)))
        return list(result.scalars().all())
