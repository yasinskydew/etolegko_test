from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyKey


class IdempotencyKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: str) -> IdempotencyKey | None:
        result = await self._session.execute(
            select(IdempotencyKey).where(IdempotencyKey.key == key)
        )
        return result.scalar_one_or_none()

    async def add(self, row: IdempotencyKey) -> IdempotencyKey:
        self._session.add(row)
        await self._session.flush()
        return row

    async def delete_for_company(self, company_id: int) -> None:
        await self._session.execute(
            delete(IdempotencyKey).where(IdempotencyKey.company_id == company_id)
        )
