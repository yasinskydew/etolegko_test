import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients.keitaro import init_keitaro, shutdown_keitaro
from app.db.session import engine
from app.errors import AppError, app_error_handler
from app.routers import auth, companies, offers


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_keitaro()
    yield
    await shutdown_keitaro()
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
