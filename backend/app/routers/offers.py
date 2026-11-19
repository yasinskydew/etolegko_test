from fastapi import APIRouter, Depends, Query

from app.deps import get_current_user, get_offers_service
from app.openapi_meta import RESP_PROTECTED
from app.schemas.company import OfferCatalogResponse
from app.services.offers_service import OffersService

router = APIRouter(tags=["offers"])


@router.get(
    "/offers",
    response_model=OfferCatalogResponse,
    summary="List offers catalog",
    description=(
        "Read-only catalog via Keitaro Admin API `GET /offers` "
        "(through `HttpKeitaroClient`). "
        "When `KEITARO_URL` is empty the list is empty (no local stub catalog). "
        "Optional substring filter `q` on offer name. "
        "No create/update/delete via this API."
    ),
    responses={
        200: {"description": "Catalog items."},
        **RESP_PROTECTED,
    },
)
async def list_offers(
    q: str | None = Query(
        default=None,
        description="Optional case-insensitive substring filter on offer name.",
        examples=["beauty"],
    ),
    _user: str = Depends(get_current_user),
    service: OffersService = Depends(get_offers_service),
) -> OfferCatalogResponse:
    return await service.list_offers(q)
