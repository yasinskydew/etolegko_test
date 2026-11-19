"""Fetch: synced snapshot without share normalize; blocked in update mode; unknown geo."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.clients.keitaro import KeitaroOffer
from tests.conftest import MockKeitaroClient, create_ready_company, offers_stream


@pytest.mark.asyncio
async def test_fetch_synced_writes_snapshot_without_normalizing_shares(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="test_yasinsky_company_fetch_sync")
    cid = company["id"]
    stream_id = offers_stream(company)["id"]
    version = company["version"]

    # Local: two offers, then push so synced; then change tracker shares to uneven 70/30.
    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "add", "offer_id": 3801, "expected_version": version},
    )
    assert r.status_code == 200, r.text
    push = await client.post(f"/companies/{cid}/sync", headers=auth_headers)
    assert push.status_code == 200, push.text
    assert offers_stream(push.json())["sync"] == "synced"

    camp_id = next(iter(mock_keitaro._campaigns))
    camp = mock_keitaro._campaigns[camp_id]
    offers_k = next(s for s in camp.streams if s.name == "offers")
    # Uneven shares that still sum to 100 — must NOT be redistributed to 50/50.
    offers_k.offers = [
        KeitaroOffer(offer_id=3749, name=None, share=70),
        KeitaroOffer(offer_id=3801, name=None, share=30),
    ]

    fetched = await client.post(f"/companies/{cid}/fetch", headers=auth_headers)
    assert fetched.status_code == 200, fetched.text
    stream = offers_stream(fetched.json())
    assert stream["sync"] == "synced"
    by_id = {o["offer_id"]: o["percent"] for o in stream["offers"] if not o["removed"]}
    assert by_id == {3749: 70, 3801: 30}


@pytest.mark.asyncio
async def test_fetch_blocked_in_update_mode(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    company = await create_ready_company(client, auth_headers, name="test_yasinsky_company_fetch_block")
    cid = company["id"]
    stream_id = offers_stream(company)["id"]

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={
            "action": "add",
            "offer_id": 3801,
            "expected_version": company["version"],
        },
    )
    assert r.status_code == 200
    assert offers_stream(r.json())["sync"] == "update_mode"

    blocked = await client.post(f"/companies/{cid}/fetch", headers=auth_headers)
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "fetch_blocked"


@pytest.mark.asyncio
async def test_fetch_unknown_geo_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="test_yasinsky_company_fetch_geo")
    cid = company["id"]
    assert offers_stream(company)["sync"] == "synced"

    camp_id = next(iter(mock_keitaro._campaigns))
    camp = mock_keitaro._campaigns[camp_id]
    google = next(s for s in camp.streams if s.schema == "redirect")
    google.filters_geo = ["ZZ"]

    resp = await client.post(f"/companies/{cid}/fetch", headers=auth_headers)
    assert resp.status_code == 422
    assert resp.json()["error"] == "unknown_geo"
