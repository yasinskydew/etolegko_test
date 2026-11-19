"""Stream offer actions: version, pin rules, restore, duplicate add."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import create_ready_company, offers_stream


def _active(offers: list[dict]) -> list[dict]:
    return [o for o in offers if not o["removed"]]


@pytest.mark.asyncio
async def test_action_version_conflict(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    company = await create_ready_company(client, auth_headers, name="act_ver")
    stream = offers_stream(company)

    resp = await client.post(
        f"/companies/{company['id']}/streams/{stream['id']}/actions",
        headers=auth_headers,
        json={
            "action": "add",
            "offer_id": 3801,
            "expected_version": company["version"] + 99,
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "version_conflict"


@pytest.mark.asyncio
async def test_set_percent_last_free_forbidden(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    company = await create_ready_company(client, auth_headers, name="act_last_free")
    stream = offers_stream(company)
    version = company["version"]

    # Only one free offer (the initial 100%) — set_percent would pin it as last free.
    resp = await client.post(
        f"/companies/{company['id']}/streams/{stream['id']}/actions",
        headers=auth_headers,
        json={
            "action": "set_percent",
            "offer_id": 3749,
            "percent": 50,
            "expected_version": version,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"


@pytest.mark.asyncio
async def test_restore_clears_pin(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    company = await create_ready_company(client, auth_headers, name="act_restore")
    stream_id = offers_stream(company)["id"]
    cid = company["id"]
    version = company["version"]

    # add second offer, pin first, remove first, restore first → pin must be false
    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "add", "offer_id": 3801, "expected_version": version},
    )
    assert r.status_code == 200, r.text
    version = r.json()["version"]

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "pin", "offer_id": 3749, "expected_version": version},
    )
    assert r.status_code == 200, r.text
    version = r.json()["version"]
    pinned = next(o for o in offers_stream(r.json())["offers"] if o["offer_id"] == 3749)
    assert pinned["pinned"] is True

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "remove", "offer_id": 3749, "expected_version": version},
    )
    assert r.status_code == 200, r.text
    version = r.json()["version"]

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "restore", "offer_id": 3749, "expected_version": version},
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
    company = await create_ready_company(client, auth_headers, name="act_dup")
    stream = offers_stream(company)

    resp = await client.post(
        f"/companies/{company['id']}/streams/{stream['id']}/actions",
        headers=auth_headers,
        json={
            "action": "add",
            "offer_id": 3749,
            "expected_version": company["version"],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "validation_error"
