from app.clients.keitaro import KeitaroClient
from app.schemas.company import OfferCatalogItem, OfferCatalogResponse


class OffersService:
    def __init__(self, keitaro: KeitaroClient) -> None:
        self._keitaro = keitaro

    async def list_offers(self, q: str | None) -> OfferCatalogResponse:
        items = await self._keitaro.list_offers(q)
        return OfferCatalogResponse(
            items=[
                OfferCatalogItem(offer_id=o.offer_id, name=o.name) for o in items
            ]
        )
