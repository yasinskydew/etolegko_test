from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.company import CompanyRepository
from app.repositories.geo import GeoRepository
from app.repositories.idempotency import IdempotencyKeyRepository
from app.repositories.stream import StreamRepository


class UnitOfWork:
    """Repositories sharing one session; the only place services commit or roll back."""

    def __init__(
        self,
        session: AsyncSession,
        companies: CompanyRepository,
        streams: StreamRepository,
        geos: GeoRepository,
        idempotency: IdempotencyKeyRepository,
    ) -> None:
        self._session = session
        self.companies = companies
        self.streams = streams
        self.geos = geos
        self.idempotency = idempotency

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
