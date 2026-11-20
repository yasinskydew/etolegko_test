from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Stream, StreamOffer, StreamType


class StreamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, stream_id: int) -> Stream | None:
        result = await self._session.execute(
            select(Stream)
            .where(Stream.id == stream_id)
            .options(selectinload(Stream.offers))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_by_company(self, company_id: int) -> list[Stream]:
        result = await self._session.execute(
            select(Stream)
            .where(Stream.company_id == company_id)
            .order_by(Stream.position)
            .options(selectinload(Stream.offers))
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def get_offers_stream(self, company_id: int) -> Stream | None:
        result = await self._session.execute(
            select(Stream)
            .where(
                Stream.company_id == company_id,
                Stream.type == StreamType.offers,
            )
            .options(selectinload(Stream.offers))
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_google_stream(self, company_id: int) -> Stream | None:
        result = await self._session.execute(
            select(Stream).where(
                Stream.company_id == company_id,
                Stream.type == StreamType.google,
            )
        )
        return result.scalar_one_or_none()

    async def add(self, stream: Stream) -> Stream:
        self._session.add(stream)
        await self._session.flush()
        return stream

    async def delete(self, stream: Stream) -> None:
        await self._session.delete(stream)
        await self._session.flush()

    async def replace_offers(
        self,
        stream_id: int,
        offers: list[StreamOffer],
    ) -> None:
        await self._session.execute(
            delete(StreamOffer).where(StreamOffer.stream_id == stream_id)
        )
        for offer in offers:
            offer.stream_id = stream_id
            self._session.add(offer)
        await self._session.flush()

    async def add_offer(self, offer: StreamOffer) -> StreamOffer:
        self._session.add(offer)
        await self._session.flush()
        return offer

    async def delete_offer(self, offer: StreamOffer) -> None:
        await self._session.delete(offer)
        await self._session.flush()
