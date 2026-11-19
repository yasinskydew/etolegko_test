"""Create company: idempotency, Keitaro rollback, stuck creating."""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.errors import AppError
from app.models import CompanyLifecycle
from tests.conftest import MockKeitaroClient


@pytest.mark.asyncio
async def test_create_idempotent_same_key_same_body(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    body = {"name": "co_idem_ok", "geo_codes": ["MX"], "offer_id": 3749}
    headers = {**auth_headers, "Idempotency-Key": "key-same"}

    first = await client.post("/companies", headers=headers, json=body)
    assert first.status_code == 201, first.text
    second = await client.post("/companies", headers=headers, json=body)
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["lifecycle"] == CompanyLifecycle.ready.value


@pytest.mark.asyncio
async def test_create_idempotency_conflict_different_payload(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    headers = {**auth_headers, "Idempotency-Key": "key-conflict"}
    first = await client.post(
        "/companies",
        headers=headers,
        json={"name": "co_a", "geo_codes": ["MX"], "offer_id": 3749},
    )
    assert first.status_code == 201, first.text

    conflict = await client.post(
        "/companies",
        headers=headers,
        json={"name": "co_b", "geo_codes": ["MX"], "offer_id": 3749},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_create_keitaro_failure_rolls_back(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    mock_keitaro.fail_create = AppError(
        502, "keitaro_bad_gateway", "tracker down"
    )
    resp = await client.post(
        "/companies",
        headers={**auth_headers, "Idempotency-Key": "key-fail"},
        json={"name": "co_fail", "geo_codes": ["MX"], "offer_id": 3749},
    )
    assert resp.status_code == 502
    assert resp.json()["error"] == "keitaro_bad_gateway"

    listed = await client.get("/companies", headers=auth_headers)
    assert listed.status_code == 200
    assert all(item["name"] != "co_fail" for item in listed.json()["items"])


@pytest.mark.asyncio
async def test_stuck_creating_blocks_actions(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Simulate hung creating row (compensation failed / finalize incomplete)."""
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        row = await conn.execute(
            text(
                "INSERT INTO company (name, lifecycle, traffic_status, version) "
                "VALUES ('stuck_co', 'creating', 'active', 1) "
                "RETURNING id"
            )
        )
        company_id = row.scalar_one()
        await conn.execute(
            text(
                "INSERT INTO stream (company_id, type, position) "
                "VALUES (:cid, 'google', 1), (:cid, 'offers', 2)"
            ),
            {"cid": company_id},
        )
        stream_row = await conn.execute(
            text(
                "SELECT id FROM stream WHERE company_id = :cid AND type = 'offers'"
            ),
            {"cid": company_id},
        )
        stream_id = stream_row.scalar_one()
    await engine.dispose()

    card = await client.get(f"/companies/{company_id}", headers=auth_headers)
    assert card.status_code == 200
    assert card.json()["lifecycle"] == "creating"

    action = await client.post(
        f"/companies/{company_id}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "add", "offer_id": 3801, "expected_version": 1},
    )
    assert action.status_code == 409
    assert action.json()["error"] == "validation_error"
