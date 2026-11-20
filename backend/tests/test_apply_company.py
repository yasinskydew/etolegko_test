"""PUT /companies/{id}: apply full draft to DB + Keitaro."""

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
async def test_legacy_endpoints_removed(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_legacy"
    )
    cid = company["id"]
    sid = offers_stream(company)["id"]
    assert "sync" not in company
    assert "sync" not in offers_stream(company)

    for method, url, body in (
        ("POST", f"/companies/{cid}/streams/{sid}/actions", {"action": "add", "offer_id": 1}),
        ("POST", f"/companies/{cid}/sync", None),
        ("POST", f"/companies/{cid}/cancel", None),
        ("PATCH", f"/companies/{cid}/geo", {"geo_codes": ["MX"]}),
    ):
        resp = await client.request(method, url, headers=auth_headers, json=body)
        assert resp.status_code in (404, 405), (method, url, resp.status_code)
