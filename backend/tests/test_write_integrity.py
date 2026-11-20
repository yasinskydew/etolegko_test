"""Keitaro write integrity: no row lock across HTTP, partial apply, failed creates, idempotency races."""

from __future__ import annotations

import os

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.clients.keitaro import KeitaroCampaign
from app.errors import AppError
from app.repositories import (
    CompanyRepository,
    IdempotencyKeyRepository,
    StreamRepository,
)
from tests.conftest import MockKeitaroClient, create_ready_company, offers_stream

TWO_OFFERS = [
    {"offer_id": 3749, "percent": 50, "pinned": False, "removed": False, "position": 1},
    {"offer_id": 3801, "percent": 50, "pinned": False, "removed": False, "position": 2},
]


def _active_offers(company: dict) -> set[tuple[int, int]]:
    return {
        (o["offer_id"], o["percent"])
        for o in offers_stream(company)["offers"]
        if not o["removed"]
    }


async def _exec(sql: str, **params: object) -> object:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), params)
            return result.scalar_one_or_none() if result.returns_rows else None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_no_row_lock_held_during_tracker_http(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="test_yasinsky_company_nolock")
    cid = company["id"]
    locked: list[object] = []

    async def grab_lock() -> None:
        locked.append(
            await _exec("SELECT id FROM company WHERE id = :id FOR UPDATE NOWAIT", id=cid)
        )

    mock_keitaro.on_tracker_write = grab_lock
    resp = await client.put(
        f"/companies/{cid}", headers=auth_headers, json={"geo_codes": ["AU"], "offers": TWO_OFFERS}
    )
    assert resp.status_code == 200, resp.text
    assert locked and all(row == cid for row in locked)

    resp = await client.post(f"/companies/{cid}/disable", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert len(locked) == 3


@pytest.mark.asyncio
async def test_partial_apply_persists_applied_geo_and_reports(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="test_yasinsky_company_partial")
    cid = company["id"]
    mock_keitaro.fail_update_offers = AppError(502, "keitaro_bad_gateway", "offers down")

    resp = await client.put(
        f"/companies/{cid}", headers=auth_headers, json={"geo_codes": ["AU"], "offers": TWO_OFFERS}
    )
    assert resp.status_code == 502, resp.text
    body = resp.json()
    assert body["error"] == "keitaro_partial_apply"
    assert set(body["fields"]) == {"geo_codes", "offers"}

    card = (await client.get(f"/companies/{cid}", headers=auth_headers)).json()
    assert card["geo_codes"] == ["AU"]
    assert _active_offers(card) == {(3749, 100)}
    assert card["drift"]["geo"] is False
    assert card["drift"]["offers"] is False


@pytest.mark.asyncio
async def test_geo_failure_changes_nothing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="test_yasinsky_company_geofail")
    cid = company["id"]
    mock_keitaro.fail_update_geo = AppError(502, "keitaro_bad_gateway", "geo down")

    resp = await client.put(
        f"/companies/{cid}", headers=auth_headers, json={"geo_codes": ["AU"], "offers": TWO_OFFERS}
    )
    assert resp.status_code == 502
    assert resp.json()["error"] == "keitaro_bad_gateway"
    assert mock_keitaro.calls["update_stream_offers"] == 0

    card = (await client.get(f"/companies/{cid}", headers=auth_headers)).json()
    assert card["geo_codes"] == ["MX"]
    assert _active_offers(card) == {(3749, 100)}


@pytest.mark.asyncio
async def test_concurrent_change_during_apply_is_409_and_drift_visible(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="test_yasinsky_company_race")
    cid = company["id"]

    async def concurrent_writer() -> None:
        mock_keitaro.on_tracker_write = None
        await _exec("UPDATE company SET updated_at = clock_timestamp() WHERE id = :id", id=cid)

    mock_keitaro.on_tracker_write = concurrent_writer
    resp = await client.put(
        f"/companies/{cid}", headers=auth_headers, json={"geo_codes": ["AU"], "offers": TWO_OFFERS}
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"] == "concurrent_update"

    card = (await client.get(f"/companies/{cid}", headers=auth_headers)).json()
    assert card["geo_codes"] == ["MX"]
    assert card["drift"]["geo"] is True
    assert card["drift"]["offers"] is True


@pytest.mark.asyncio
async def test_idempotency_race_same_payload_replays(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"name": "test_yasinsky_company_idrace", "geo_codes": ["MX"], "offer_id": 3749}
    headers = {**auth_headers, "Idempotency-Key": "race-key"}
    first = await client.post("/companies", headers=headers, json=body)
    assert first.status_code == 201, first.text

    _simulate_lost_race(monkeypatch, mock_keitaro)
    second = await client.post("/companies", headers=headers, json=body)
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_idempotency_race_other_payload_is_conflict_not_name_taken(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = {**auth_headers, "Idempotency-Key": "race-key-2"}
    first = await client.post(
        "/companies",
        headers=headers,
        json={"name": "test_yasinsky_company_idr_a", "geo_codes": ["MX"], "offer_id": 3749},
    )
    assert first.status_code == 201, first.text

    _simulate_lost_race(monkeypatch, mock_keitaro)
    second = await client.post(
        "/companies",
        headers=headers,
        json={"name": "test_yasinsky_company_idr_b", "geo_codes": ["MX"], "offer_id": 3749},
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"] == "idempotency_conflict"


@pytest.mark.asyncio
async def test_finalize_failure_marks_failed_then_retry_recreates(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = StreamRepository.get_google_stream
    state = {"fail": True}

    async def flaky(self: StreamRepository, company_id: int):  # type: ignore[no-untyped-def]
        if state["fail"]:
            state["fail"] = False
            raise RuntimeError("db hiccup")
        return await original(self, company_id)

    monkeypatch.setattr(StreamRepository, "get_google_stream", flaky)
    mock_keitaro.fail_delete = AppError(502, "keitaro_bad_gateway", "delete down")
    body = {"name": "test_yasinsky_company_failed", "geo_codes": ["MX"], "offer_id": 3749}
    headers = {**auth_headers, "Idempotency-Key": "fail-key"}

    resp = await client.post("/companies", headers=headers, json=body)
    assert resp.status_code == 502, resp.text
    listed = (await client.get("/companies", headers=auth_headers)).json()["items"]
    failed = [c for c in listed if c["name"] == body["name"]]
    assert len(failed) == 1 and failed[0]["lifecycle"] == "failed"
    orphan_campaign = next(iter(mock_keitaro._campaigns))

    mock_keitaro.fail_delete = None
    retry = await client.post("/companies", headers=headers, json=body)
    assert retry.status_code == 201, retry.text
    assert retry.json()["lifecycle"] == "ready"
    assert retry.json()["id"] != failed[0]["id"]
    assert orphan_campaign not in mock_keitaro._campaigns


@pytest.mark.asyncio
async def test_stale_creating_becomes_failed_and_name_is_reusable(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    stale_id = await _exec(
        "INSERT INTO company (name, lifecycle, traffic_status, updated_at) "
        "VALUES ('test_yasinsky_company_stale', 'creating', 'active', now() - interval '1 hour') "
        "RETURNING id"
    )
    other_id = await _exec(
        "INSERT INTO company (name, lifecycle, traffic_status, updated_at) "
        "VALUES ('test_yasinsky_company_stale2', 'creating', 'active', now() - interval '1 hour') "
        "RETURNING id"
    )

    created = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_stale", idempotency_key="stale-key"
    )
    assert created["lifecycle"] == "ready"
    assert (await client.get(f"/companies/{stale_id}", headers=auth_headers)).status_code == 404
    other = (await client.get(f"/companies/{other_id}", headers=auth_headers)).json()
    assert other["lifecycle"] == "failed"

    apply = await client.put(
        f"/companies/{other_id}",
        headers=auth_headers,
        json={"geo_codes": ["MX"], "offers": TWO_OFFERS},
    )
    assert apply.status_code == 409


def _simulate_lost_race(monkeypatch: pytest.MonkeyPatch, mock: MockKeitaroClient) -> None:
    """Make pre-checks miss the committed winner, as in two concurrent requests."""
    original_get = IdempotencyKeyRepository.get
    state = {"calls": 0}

    async def racy_get(self: IdempotencyKeyRepository, key: str):  # type: ignore[no-untyped-def]
        state["calls"] += 1
        if state["calls"] == 1:
            return None
        return await original_get(self, key)

    async def no_duplicate(self: CompanyRepository, name: str) -> None:
        return None

    async def not_in_tracker(name: str) -> KeitaroCampaign | None:
        return None

    monkeypatch.setattr(IdempotencyKeyRepository, "get", racy_get)
    monkeypatch.setattr(CompanyRepository, "get_by_name_lower", no_duplicate)
    monkeypatch.setattr(mock, "find_campaign_by_name", not_in_tracker)
