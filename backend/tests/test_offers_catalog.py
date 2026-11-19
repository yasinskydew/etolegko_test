"""GET /offers catalog must come from KeitaroClient.list_offers (not local stubs)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.clients.keitaro import KeitaroOffer
from tests.conftest import MockKeitaroClient


@pytest.mark.asyncio
async def test_offers_endpoint_uses_keitaro_list(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    async def fake_list(q: str | None = None) -> list[KeitaroOffer]:
        items = [
            KeitaroOffer(offer_id=101, name="Real Offer A", country=["MX"]),
            KeitaroOffer(offer_id=202, name="Real Offer B", country=["US", "CA"]),
        ]
        if q:
            ql = q.lower()
            items = [o for o in items if o.name and ql in o.name.lower()]
        return items

    mock_keitaro.list_offers = fake_list  # type: ignore[method-assign]

    r = await client.get("/offers", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert [i["offer_id"] for i in body["items"]] == [101, 202]
    assert body["items"][0]["country"] == ["MX"]
    assert body["items"][1]["country"] == ["US", "CA"]

    r2 = await client.get("/offers", params={"q": "offer b"}, headers=auth_headers)
    assert r2.status_code == 200
    assert [i["offer_id"] for i in r2.json()["items"]] == [202]


@pytest.mark.asyncio
async def test_noop_catalog_is_empty_not_stubbed(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    r = await client.get("/offers", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert mock_keitaro.noop is True
