from app.errors import AppError
from app.repositories import UserRepository
from app.schemas.auth import LoginRequest, LoginResponse
from app.security import create_access_token, verify_password


class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    async def login(self, body: LoginRequest) -> LoginResponse:
        user = await self._users.get_by_username(body.username)
        if user is None or not verify_password(body.password, user.password_hash):
            raise AppError(401, "unauthorized", "Invalid username or password.")
        token = create_access_token(subject=user.username)
        return LoginResponse(access_token=token)
