from fastapi import APIRouter, Depends, Header, Query, Response

from app.deps import get_company_service, get_current_user
from app.schemas.company import (
    CompanyListResponse,
    CompanyOut,
    CreateCompanyRequest,
    GeoPatchRequest,
    StatsOut,
    StreamActionRequest,
    VersionBody,
)
from app.services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyListResponse:
    return await service.list_companies(q=q, page=page, page_size=page_size)


@router.post("", response_model=CompanyOut)
async def create_company(
    body: CreateCompanyRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    company, status = await service.create_company(body, idempotency_key or "")
    response.status_code = status
    return company


@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(
    company_id: int,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.get_company(company_id)


@router.get("/{company_id}/stats", response_model=StatsOut)
async def company_stats(
    company_id: int,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> StatsOut:
    return await service.stats(company_id)


@router.post(
    "/{company_id}/streams/{stream_id}/actions",
    response_model=CompanyOut,
)
async def stream_actions(
    company_id: int,
    stream_id: int,
    body: StreamActionRequest,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.apply_action(company_id, stream_id, body)


@router.post("/{company_id}/sync", response_model=CompanyOut)
async def push_company(
    company_id: int,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.push(company_id)


@router.post("/{company_id}/cancel", response_model=CompanyOut)
async def cancel_company(
    company_id: int,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.cancel(company_id)


@router.post("/{company_id}/fetch", response_model=CompanyOut)
async def fetch_company(
    company_id: int,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.fetch(company_id)


@router.patch("/{company_id}/geo", response_model=CompanyOut)
async def patch_geo(
    company_id: int,
    body: GeoPatchRequest,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.patch_geo(company_id, body)


@router.post("/{company_id}/enable", response_model=CompanyOut)
async def enable_company(
    company_id: int,
    body: VersionBody,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.set_traffic(company_id, body, enable=True)


@router.post("/{company_id}/disable", response_model=CompanyOut)
async def disable_company(
    company_id: int,
    body: VersionBody,
    _user: str = Depends(get_current_user),
    service: CompanyService = Depends(get_company_service),
) -> CompanyOut:
    return await service.set_traffic(company_id, body, enable=False)
