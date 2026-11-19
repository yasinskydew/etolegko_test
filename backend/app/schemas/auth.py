from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials for `POST /auth/login`."""

    username: str = Field(min_length=1, description="Admin username from seed / env.")
    password: str = Field(min_length=1, description="Plain password; verified against stored hash.")


class LoginResponse(BaseModel):
    """JWT access token. No refresh token."""

    access_token: str = Field(description="Signed JWT to send as `Authorization: Bearer`.")
    token_type: str = Field(default="bearer", description="Always `bearer`.")
