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
    UserRepository,
)
from app.security import decode_access_token
from app.services.auth_service import AuthService
from app.services.company_service import CompanyService
from app.services.offers_service import OffersService
import jwt


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


def get_company_service(
    session: AsyncSession = Depends(get_session),
    keitaro: KeitaroClient = Depends(get_keitaro),
) -> CompanyService:
    return CompanyService(
        session=session,
        company_repo=CompanyRepository(session),
        stream_repo=StreamRepository(session),
        geo_repo=GeoRepository(session),
        idempotency_repo=IdempotencyKeyRepository(session),
        keitaro=keitaro,
    )


def get_offers_service(
    keitaro: KeitaroClient = Depends(get_keitaro),
) -> OffersService:
    return OffersService(keitaro=keitaro)
