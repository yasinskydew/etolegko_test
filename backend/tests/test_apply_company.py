"""PUT /companies/{id}: apply full draft to DB + Keitaro; Cancel is FE-local no-op."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.errors import AppError
from tests.conftest import MockKeitaroClient, create_ready_company, offers_stream


@pytest.mark.asyncio
async def test_put_apply_writes_offers_and_geo_to_keitaro(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_apply", geo_codes=["MX"]
    )
    cid = company["id"]

    resp = await client.put(
        f"/companies/{cid}",
        headers=auth_headers,
        json={
            "geo_codes": ["MX", "AU"],
            "offers": [
                {
                    "offer_id": 3749,
                    "percent": 70,
                    "pinned": True,
                    "removed": False,
                    "position": 1,
                },
                {
                    "offer_id": 3801,
                    "percent": 30,
                    "pinned": False,
                    "removed": False,
                    "position": 2,
                },
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    assert mock_keitaro.calls["update_stream_offers"] >= 1
    assert mock_keitaro.calls["update_google_geo"] >= 1

    body = resp.json()
    assert body["geo_codes"] == ["MX", "AU"]
    assert "version" not in body
    assert offers_stream(body)["sync"] == "synced"
    by_id = {
        o["offer_id"]: o
        for o in offers_stream(body)["offers"]
        if not o["removed"]
    }
    assert by_id[3749]["percent"] == 70 and by_id[3749]["pinned"] is True
    assert by_id[3801]["percent"] == 30


@pytest.mark.asyncio
async def test_put_apply_keeps_removed_archive(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_apply_arch"
    )
    cid = company["id"]

    resp = await client.put(
        f"/companies/{cid}",
        headers=auth_headers,
        json={
            "geo_codes": ["MX"],
            "offers": [
                {
                    "offer_id": 3749,
                    "percent": 100,
                    "pinned": False,
                    "removed": False,
                    "position": 1,
                },
                {
                    "offer_id": 3801,
                    "percent": 40,
                    "pinned": False,
                    "removed": True,
                    "position": 2,
                },
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    # Only active offers sent to tracker.
    camp_id = next(iter(mock_keitaro._campaigns))
    offers_k = next(
        s for s in mock_keitaro._campaigns[camp_id].streams if s.name == "offers"
    )
    assert {(o.offer_id, o.share) for o in offers_k.offers} == {(3749, 100)}

    archived = [
        o for o in offers_stream(resp.json())["offers"] if o["offer_id"] == 3801
    ]
    assert len(archived) == 1 and archived[0]["removed"] is True


@pytest.mark.asyncio
async def test_put_apply_keitaro_failure_leaves_db(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_apply_fail"
    )
    cid = company["id"]
    before = offers_stream(company)["offers"]
    mock_keitaro.fail_update_offers = AppError(
        502, "keitaro_bad_gateway", "apply failed"
    )

    resp = await client.put(
        f"/companies/{cid}",
        headers=auth_headers,
        json={
            "geo_codes": ["MX"],
            "offers": [
                {
                    "offer_id": 3749,
                    "percent": 50,
                    "pinned": False,
                    "removed": False,
                    "position": 1,
                },
                {
                    "offer_id": 3801,
                    "percent": 50,
                    "pinned": False,
                    "removed": False,
                    "position": 2,
                },
            ],
        },
    )
    assert resp.status_code == 502

    card = await client.get(f"/companies/{cid}", headers=auth_headers)
    assert card.status_code == 200
    after = offers_stream(card.json())["offers"]
    assert {(o["offer_id"], o["percent"], o["removed"]) for o in after} == {
        (o["offer_id"], o["percent"], o["removed"]) for o in before
    }


@pytest.mark.asyncio
async def test_cancel_is_noop_without_keitaro(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_cancel"
    )
    cid = company["id"]
    stream_id = offers_stream(company)["id"]

    edited = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "add", "offer_id": 3801},
    )
    assert edited.status_code == 200
    working = offers_stream(edited.json())["offers"]

    mutating = (
        "create",
        "delete",
        "update_stream_offers",
        "enable",
        "disable",
        "update_google_geo",
    )
    before = {k: mock_keitaro.calls[k] for k in mutating}
    cancel = await client.post(f"/companies/{cid}/cancel", headers=auth_headers)
    assert cancel.status_code == 200, cancel.text
    assert {k: mock_keitaro.calls[k] for k in mutating} == before
    # Cancel no longer restores snapshot — returns current DB (edited) state.
    assert {
        (o["offer_id"], o["percent"], o["removed"])
        for o in offers_stream(cancel.json())["offers"]
    } == {(o["offer_id"], o["percent"], o["removed"]) for o in working}
