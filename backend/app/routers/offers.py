from fastapi import APIRouter, Depends, Query

from app.deps import get_current_user, get_offers_service
from app.schemas.company import OfferCatalogResponse
from app.services.offers_service import OffersService

router = APIRouter(tags=["offers"])


@router.get("/offers", response_model=OfferCatalogResponse)
async def list_offers(
    q: str | None = Query(default=None),
    _user: str = Depends(get_current_user),
    service: OffersService = Depends(get_offers_service),
) -> OfferCatalogResponse:
    return await service.list_offers(q)
