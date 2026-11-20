"""Fetch from Keitaro: writes local state without share normalize; unknown geo."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.clients.keitaro import KeitaroOffer
from tests.conftest import MockKeitaroClient, create_ready_company, offers_stream


@pytest.mark.asyncio
async def test_fetch_writes_tracker_shares_without_normalizing(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_fetch_sync"
    )
    cid = company["id"]

    applied = await client.put(
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
    assert applied.status_code == 200, applied.text

    camp_id = next(iter(mock_keitaro._campaigns))
    camp = mock_keitaro._campaigns[camp_id]
    offers_k = next(s for s in camp.streams if s.name == "offers")
    offers_k.offers = [
        KeitaroOffer(offer_id=3749, name=None, share=70),
        KeitaroOffer(offer_id=3801, name=None, share=30),
    ]

    fetched = await client.post(f"/companies/{cid}/fetch", headers=auth_headers)
    assert fetched.status_code == 200, fetched.text
    stream = offers_stream(fetched.json())
    by_id = {o["offer_id"]: o["percent"] for o in stream["offers"] if not o["removed"]}
    assert by_id == {3749: 70, 3801: 30}


@pytest.mark.asyncio
async def test_fetch_unknown_geo_422(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(
        client, auth_headers, name="test_yasinsky_company_fetch_geo"
    )
    cid = company["id"]

    camp_id = next(iter(mock_keitaro._campaigns))
    camp = mock_keitaro._campaigns[camp_id]
    google = next(s for s in camp.streams if s.schema == "redirect")
    google.filters_geo = ["ZZ"]

    resp = await client.post(f"/companies/{cid}/fetch", headers=auth_headers)
    assert resp.status_code == 422
    assert resp.json()["error"] == "unknown_geo"
