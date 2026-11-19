"""Fixtures for API integration tests with mocked KeitaroClient."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Load .env before importing app modules that read DATABASE_URL at import time.
_ROOT = Path(__file__).resolve().parents[2]
_ENV = _ROOT / ".env"
if _ENV.exists():
    for line in _ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://app:changeme@localhost:5432/etolegko",
)
os.environ["JWT_SECRET"] = "changeme-test-secret-key-32bytes!!"
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "changeme")
os.environ.setdefault("KEITARO_URL", "")
os.environ.setdefault("GOOGLE_URL", "https://google.com")


def _isolate_test_database_url() -> str:
    """Point tests at etolegko_test so TRUNCATE never wipes the app DB."""
    explicit = (os.environ.get("TEST_DATABASE_URL") or "").strip()
    if explicit:
        os.environ["DATABASE_URL"] = explicit
        return explicit
    from sqlalchemy.engine.url import make_url

    url = make_url(os.environ["DATABASE_URL"])
    if (url.database or "") != "etolegko_test":
        url = url.set(database="etolegko_test")
        os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    return os.environ["DATABASE_URL"]


_TEST_DB_URL = _isolate_test_database_url()


def _assert_not_app_database(url: str) -> None:
    from sqlalchemy.engine.url import make_url

    db_name = make_url(url).database or ""
    if db_name == "etolegko" and not os.environ.get("TEST_ALLOW_APP_DB"):
        raise RuntimeError(
            "Refusing to TRUNCATE app database 'etolegko'. "
            "Tests must use etolegko_test (or set TEST_DATABASE_URL / TEST_ALLOW_APP_DB=1)."
        )


from app.clients.keitaro import (  # noqa: E402
    CreatedCampaign,
    KeitaroCampaign,
    NoopKeitaroClient,
)
from app.db import session as db_session  # noqa: E402
from app.deps import get_keitaro  # noqa: E402
from app.main import app  # noqa: E402


def _rebind_db_engine() -> None:
    """Bind app session factory to a NullPool engine on the current event loop."""
    _assert_not_app_database(os.environ["DATABASE_URL"])
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    db_session.engine = engine
    db_session.async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


class MockKeitaroClient(NoopKeitaroClient):
    """Noop Keitaro with injectable failures and call counters."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_create: Exception | None = None
        self.fail_update_offers: Exception | None = None
        self.fail_enable: Exception | None = None
        self.fail_disable: Exception | None = None
        self.fail_delete: Exception | None = None
        self.calls: dict[str, int] = {
            "create": 0,
            "delete": 0,
            "update_stream_offers": 0,
            "enable": 0,
            "disable": 0,
            "get_campaign": 0,
            "update_google_geo": 0,
        }

    async def create_company_campaign(
        self,
        *,
        name: str,
        geo_codes: list[str],
        offer_id: int,
        google_url: str,
    ) -> CreatedCampaign:
        self.calls["create"] += 1
        if self.fail_create is not None:
            raise self.fail_create
        return await super().create_company_campaign(
            name=name,
            geo_codes=geo_codes,
            offer_id=offer_id,
            google_url=google_url,
        )

    async def delete_campaign(self, campaign_id: int) -> None:
        self.calls["delete"] += 1
        if self.fail_delete is not None:
            raise self.fail_delete
        await super().delete_campaign(campaign_id)

    async def update_stream_offers(
        self,
        *,
        campaign_id: int,
        stream_id: int,
        offers: list[tuple[int, int]],
    ) -> None:
        self.calls["update_stream_offers"] += 1
        if self.fail_update_offers is not None:
            raise self.fail_update_offers
        await super().update_stream_offers(
            campaign_id=campaign_id,
            stream_id=stream_id,
            offers=offers,
        )

    async def enable_campaign(self, campaign_id: int) -> None:
        self.calls["enable"] += 1
        if self.fail_enable is not None:
            raise self.fail_enable
        await super().enable_campaign(campaign_id)

    async def disable_campaign(self, campaign_id: int) -> None:
        self.calls["disable"] += 1
        if self.fail_disable is not None:
            raise self.fail_disable
        await super().disable_campaign(campaign_id)

    async def get_campaign(self, campaign_id: int) -> KeitaroCampaign | None:
        self.calls["get_campaign"] += 1
        return await super().get_campaign(campaign_id)

    async def update_google_geo(
        self,
        *,
        campaign_id: int,
        stream_id: int,
        geo_codes: list[str],
    ) -> None:
        self.calls["update_google_geo"] += 1
        await super().update_google_geo(
            campaign_id=campaign_id,
            stream_id=stream_id,
            geo_codes=geo_codes,
        )


@pytest.fixture
def mock_keitaro() -> Iterator[MockKeitaroClient]:
    client = MockKeitaroClient()
    app.dependency_overrides[get_keitaro] = lambda: client
    yield client
    app.dependency_overrides.pop(get_keitaro, None)


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_database() -> None:
    """Ensure isolated test DB schema exists (alembic upgrade head)."""
    import subprocess
    import sys

    _assert_not_app_database(_TEST_DB_URL)
    env = os.environ.copy()
    env["DATABASE_URL"] = _TEST_DB_URL
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        check=True,
    )


@pytest_asyncio.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    """Truncate mutable tables before each test; keep geo + admin user."""
    _rebind_db_engine()
    async with db_session.engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "stream_offer_snapshot, stream_offer, stream, "
                "company_geo, idempotency_key, company "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield
    await db_session.engine.dispose()


@pytest_asyncio.fixture
async def client(mock_keitaro: MockKeitaroClient) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD", "changeme")
    resp = await client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def offers_stream(company: dict) -> dict:
    for stream in company["streams"]:
        if stream["type"] == "offers":
            return stream
    raise AssertionError("offers stream missing")


async def create_ready_company(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str = "test_yasinsky_company",
    geo_codes: list[str] | None = None,
    offer_id: int = 3749,
    idempotency_key: str | None = None,
) -> dict:
    key = idempotency_key or f"idem-{name}"
    resp = await client.post(
        "/companies",
        headers={**headers, "Idempotency-Key": key},
        json={
            "name": name,
            "geo_codes": geo_codes or ["MX"],
            "offer_id": offer_id,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
