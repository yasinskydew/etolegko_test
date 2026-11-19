from fastapi import APIRouter, Depends, status

from app.deps import get_auth_service
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.errors import ErrorBody
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login",
    description=(
        "Exchange username/password for a JWT access token. "
        "No refresh token; logout is client-side (discard the token). "
        "Invalid credentials → `401 unauthorized`."
    ),
    responses={
        200: {"description": "Token issued."},
        401: {
            "model": ErrorBody,
            "description": "Wrong username or password (`unauthorized`).",
        },
    },
)
async def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    return await service.login(body)
