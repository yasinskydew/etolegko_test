import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.clients.keitaro import init_keitaro, shutdown_keitaro
from app.db import session as db_session
from app.db.session import engine
from app.errors import (
    AppError,
    app_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.openapi_meta import APP_DESCRIPTION, OPENAPI_TAGS
from app.repositories import CompanyRepository
from app.routers import auth, companies, offers
from app.schemas.errors import HealthOut
from app.services.companies import CREATING_TTL

logger = logging.getLogger(__name__)


async def _fail_stale_creating() -> None:
    try:
        async with db_session.async_session_factory() as session:
            count = await CompanyRepository(session).fail_stale_creating(CREATING_TTL)
            await session.commit()
        if count:
            logger.warning("Marked %s stale creating companies as failed", count)
    except Exception:
        logger.exception("Stale creating sweep failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_keitaro()
    await _fail_stale_creating()
    yield
    await shutdown_keitaro()
    await engine.dispose()


app = FastAPI(
    title="etolegko API",
    description=APP_DESCRIPTION,
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
    contact={"name": "etolegko_test"},
    license_info={"name": "Proprietary"},
)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

cors_origin = os.getenv("CORS_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(offers.router)


@app.get(
    "/health",
    response_model=HealthOut,
    tags=["health"],
    summary="Health check",
    description="Liveness probe for compose / load balancers. No JWT required.",
    responses={200: {"description": "Service is up."}},
)
def health() -> HealthOut:
    return HealthOut(status="ok")


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "HTTPBearer"
    ] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Paste the `access_token` from `POST /auth/login`.",
    }
    # Apply bearer security to all paths except health + login.
    public = {("/health", "get"), ("/auth/login", "post")}
    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            if method.startswith("x-") or not isinstance(operation, dict):
                continue
            if (path, method) in public:
                operation["security"] = []
            else:
                operation["security"] = [{"HTTPBearer": []}]
    # Validation errors use ErrorBody (see validation_error_handler), not FastAPI's default.
    for name in ("HTTPValidationError", "ValidationError"):
        schema["components"].get("schemas", {}).pop(name, None)
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]
