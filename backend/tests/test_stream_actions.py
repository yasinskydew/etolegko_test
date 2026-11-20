"""Offers-stream actions (no expected_version after system update 1)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import create_ready_company, offers_stream


@pytest.mark.asyncio
async def test_set_percent_over_pinned_cap_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_act_cap"
    )
    stream = offers_stream(company)
    cid = company["id"]
    sid = stream["id"]

    add = await client.post(
        f"/companies/{cid}/streams/{sid}/actions",
        headers=auth_headers,
        json={"action": "add", "offer_id": 3801},
    )
    assert add.status_code == 200, add.text

    pin = await client.post(
        f"/companies/{cid}/streams/{sid}/actions",
        headers=auth_headers,
        json={"action": "pin", "offer_id": 3749},
    )
    assert pin.status_code == 200, pin.text

    # Initial share after add is 50/50; pinning 3749 keeps 50.
    # Setting free offer to 60 → pinned would be 50+60 > 100.
    resp = await client.post(
        f"/companies/{cid}/streams/{sid}/actions",
        headers=auth_headers,
        json={
            "action": "set_percent",
            "offer_id": 3801,
            "percent": 60,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


@pytest.mark.asyncio
async def test_restore_clears_pin(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_act_restore"
    )
    stream_id = offers_stream(company)["id"]
    cid = company["id"]

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "add", "offer_id": 3801},
    )
    assert r.status_code == 200, r.text

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "pin", "offer_id": 3749},
    )
    assert r.status_code == 200, r.text
    pinned = next(
        o for o in offers_stream(r.json())["offers"] if o["offer_id"] == 3749
    )
    assert pinned["pinned"] is True

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "remove", "offer_id": 3749},
    )
    assert r.status_code == 200, r.text

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "restore", "offer_id": 3749},
    )
    assert r.status_code == 200, r.text
    restored = next(
        o for o in offers_stream(r.json())["offers"] if o["offer_id"] == 3749
    )
    assert restored["removed"] is False
    assert restored["pinned"] is False


@pytest.mark.asyncio
async def test_add_active_offer_twice_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_act_dup"
    )
    stream = offers_stream(company)

    resp = await client.post(
        f"/companies/{company['id']}/streams/{stream['id']}/actions",
        headers=auth_headers,
        json={"action": "add", "offer_id": 3749},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"
