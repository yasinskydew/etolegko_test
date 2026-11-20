import os

import jwt
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.keitaro import KeitaroClient, get_keitaro_singleton
from app.db.session import get_session
from app.errors import AppError
from app.repositories import (
    CompanyRepository,
    GeoRepository,
    IdempotencyKeyRepository,
    StreamRepository,
    UnitOfWork,
    UserRepository,
)
from app.security import decode_access_token
from app.services.auth_service import AuthService
from app.services.companies import (
    ApplyCompanyDraftUseCase,
    CompanyQueryService,
    CompanyValidator,
    CompanyWriteGuard,
    CreateCompanyUseCase,
    FetchFromKeitaroUseCase,
    TrafficService,
)
from app.services.offers_service import OffersService


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(401, "unauthorized", "Missing or invalid Authorization header.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise AppError(401, "unauthorized", "Invalid or expired token.") from exc
    subject = payload.get("sub")
    if not subject:
        raise AppError(401, "unauthorized", "Invalid token payload.")
    return str(subject)


def get_keitaro() -> KeitaroClient:
    return get_keitaro_singleton()


def get_auth_service(
    session: AsyncSession = Depends(get_session),
) -> AuthService:
    return AuthService(user_repo=UserRepository(session))


def get_uow(session: AsyncSession = Depends(get_session)) -> UnitOfWork:
    return UnitOfWork(
        session=session,
        companies=CompanyRepository(session),
        streams=StreamRepository(session),
        geos=GeoRepository(session),
        idempotency=IdempotencyKeyRepository(session),
    )


def get_google_url() -> str:
    return os.environ.get("GOOGLE_URL", "https://google.com")


def get_validator(uow: UnitOfWork = Depends(get_uow)) -> CompanyValidator:
    return CompanyValidator(geos=uow.geos)


def get_write_guard(uow: UnitOfWork = Depends(get_uow)) -> CompanyWriteGuard:
    return CompanyWriteGuard(uow=uow)


def get_company_queries(
    uow: UnitOfWork = Depends(get_uow),
    keitaro: KeitaroClient = Depends(get_keitaro),
    guard: CompanyWriteGuard = Depends(get_write_guard),
) -> CompanyQueryService:
    return CompanyQueryService(uow=uow, keitaro=keitaro, guard=guard)


def get_create_company(
    uow: UnitOfWork = Depends(get_uow),
    keitaro: KeitaroClient = Depends(get_keitaro),
    validator: CompanyValidator = Depends(get_validator),
    guard: CompanyWriteGuard = Depends(get_write_guard),
    queries: CompanyQueryService = Depends(get_company_queries),
    google_url: str = Depends(get_google_url),
) -> CreateCompanyUseCase:
    return CreateCompanyUseCase(
        uow=uow,
        keitaro=keitaro,
        validator=validator,
        guard=guard,
        queries=queries,
        google_url=google_url,
    )


def get_apply_company(
    uow: UnitOfWork = Depends(get_uow),
    keitaro: KeitaroClient = Depends(get_keitaro),
    validator: CompanyValidator = Depends(get_validator),
    guard: CompanyWriteGuard = Depends(get_write_guard),
    queries: CompanyQueryService = Depends(get_company_queries),
) -> ApplyCompanyDraftUseCase:
    return ApplyCompanyDraftUseCase(
        uow=uow, keitaro=keitaro, validator=validator, guard=guard, queries=queries
    )


def get_fetch_company(
    uow: UnitOfWork = Depends(get_uow),
    keitaro: KeitaroClient = Depends(get_keitaro),
    validator: CompanyValidator = Depends(get_validator),
    guard: CompanyWriteGuard = Depends(get_write_guard),
    queries: CompanyQueryService = Depends(get_company_queries),
) -> FetchFromKeitaroUseCase:
    return FetchFromKeitaroUseCase(
        uow=uow, keitaro=keitaro, validator=validator, guard=guard, queries=queries
    )


def get_traffic_service(
    uow: UnitOfWork = Depends(get_uow),
    keitaro: KeitaroClient = Depends(get_keitaro),
    guard: CompanyWriteGuard = Depends(get_write_guard),
    queries: CompanyQueryService = Depends(get_company_queries),
) -> TrafficService:
    return TrafficService(uow=uow, keitaro=keitaro, guard=guard, queries=queries)


def get_offers_service(
    keitaro: KeitaroClient = Depends(get_keitaro),
) -> OffersService:
    return OffersService(keitaro=keitaro)
