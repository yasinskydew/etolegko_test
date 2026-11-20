from fastapi import APIRouter, Depends, Header, Path, Query, Response, status

from app.deps import get_company_service, get_current_user
from app.openapi_meta import RESP_COMPANY, RESP_PROTECTED
from app.schemas.company import (
    CompanyApplyRequest,
    CompanyListResponse,
    CompanyOut,
    CreateCompanyRequest,
    StatsOut,
)
from app.services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get(
    "",
    response_model=CompanyListResponse,
    summary="List companies",
    description=(
        "Paginated companies from the local database only "
        "(campaigns created only in Keitaro never appear)."
    ),
    responses={200: {"description": "Page of companies."}, **RESP_PROTECTED},
)
async def list_companies(
    q: str | None = Query(
        default=None,
        description="Case-insensitive substring filter on company name.",
    ),
    page: int = Query(default=1, ge=1, description="1-based page index."),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Page size (max 100).",
    ),
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyListResponse:
    return await service.list_companies(q=q, page=page, page_size=page_size)


@router.post(
    "",
    response_model=CompanyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create company",
    description=(
        "Create a company with Idempotency-Key. "
        "Creates Keitaro campaign with `google` (geo filter → GOOGLE_URL) and "
        "`offers` (single offer at 100%) streams. "
        "Same key + same body → `200` with existing company; "
        "same key + different body → `409 idempotency_conflict`. "
        "Tracker failure removes the reserved row; if the tracker campaign cannot be "
        "rolled back the company becomes `failed` and the same request can be retried. "
        "`creating` rows older than 5 minutes are marked `failed`."
    ),
    responses={
        201: {"description": "Company created (`lifecycle=ready`)."},
        200: {"description": "Idempotent replay of the same key and payload."},
        **RESP_COMPANY,
    },
)
async def create_company(
    body: CreateCompanyRequest,
    response: Response,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        description="Required unique key for create idempotency.",
    ),
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    company, status_code = await service.create_company(body, idempotency_key or "")
    response.status_code = status_code
    return company


@router.get(
    "/{company_id}",
    response_model=CompanyOut,
    summary="Get company card",
    description=(
        "Full company including streams, archive offers and computed `drift`."
    ),
    responses={200: {"description": "Company card."}, **RESP_COMPANY},
)
async def get_company(
    company_id: int = Path(description="Local company id.", ge=1),
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.get_company(company_id)


@router.put(
    "/{company_id}",
    response_model=CompanyOut,
    summary="Apply company draft (Push)",
    description=(
        "Write full desired geo + offers state to Keitaro, then DB. "
        "No DB lock is held during tracker calls. Geo applied but offers failed → "
        "`502 keitaro_partial_apply` with only geo saved. Company changed meanwhile → "
        "`409 concurrent_update`; differences show up as `drift`."
    ),
    responses={200: {"description": "Applied to DB and tracker."}, **RESP_COMPANY},
)
async def apply_company(
    company_id: int = Path(description="Local company id.", ge=1),
    body: CompanyApplyRequest = ...,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.apply(company_id, body)


@router.get(
    "/{company_id}/stats",
    response_model=StatsOut,
    summary="Company stats from Keitaro",
    description=(
        "Clicks / uniques / bots from the tracker. Values may be `null`. "
        "Not stored locally and does not affect Push."
    ),
    responses={200: {"description": "Stats snapshot."}, **RESP_COMPANY},
)
async def company_stats(
    company_id: int = Path(description="Local company id.", ge=1),
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> StatsOut:
    return await service.stats(company_id)


@router.post(
    "/{company_id}/fetch",
    response_model=CompanyOut,
    summary="Fetch streams from Keitaro",
    description=(
        "Pull offers / geo / traffic / plain streams from Keitaro into local DB. "
        "Unknown geo code → `422 unknown_geo` and full rollback."
    ),
    responses={200: {"description": "Local state updated."}, **RESP_COMPANY},
)
async def fetch_company(
    company_id: int = Path(description="Local company id.", ge=1),
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.fetch(company_id)


@router.post(
    "/{company_id}/enable",
    response_model=CompanyOut,
    summary="Enable traffic",
    description=(
        "Keitaro-first enable of the campaign, then set `traffic_status=active`. "
        "Already-active → `200` without tracker write."
    ),
    responses={200: {"description": "Traffic enabled."}, **RESP_COMPANY},
)
async def enable_company(
    company_id: int = Path(description="Local company id.", ge=1),
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.set_traffic(company_id, enable=True)


@router.post(
    "/{company_id}/disable",
    response_model=CompanyOut,
    summary="Disable traffic",
    description=(
        "Keitaro-first disable of the campaign, then set `traffic_status=disabled`. "
        "Already-disabled → `200` without tracker write."
    ),
    responses={200: {"description": "Traffic disabled."}, **RESP_COMPANY},
)
async def disable_company(
    company_id: int = Path(description="Local company id.", ge=1),
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.set_traffic(company_id, enable=False)
