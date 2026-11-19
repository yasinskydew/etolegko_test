"""Enable/disable: Keitaro first; offer shares unchanged."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.errors import AppError
from tests.conftest import MockKeitaroClient, create_ready_company, offers_stream


def _share_map(company: dict) -> dict[int, tuple[int, bool, bool]]:
    stream = offers_stream(company)
    return {
        o["offer_id"]: (o["percent"], o["pinned"], o["removed"])
        for o in stream["offers"]
    }


@pytest.mark.asyncio
async def test_disable_keitaro_first_success_preserves_shares(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="traf_ok")
    shares_before = _share_map(company)

    resp = await client.post(
        f"/companies/{company['id']}/disable",
        headers=auth_headers,
        json={"expected_version": company["version"]},
    )
    assert resp.status_code == 200, resp.text
    assert mock_keitaro.calls["disable"] == 1
    body = resp.json()
    assert body["traffic_status"] == "disabled"
    assert body["version"] == company["version"] + 1
    assert _share_map(body) == shares_before


@pytest.mark.asyncio
async def test_disable_keitaro_failure_leaves_local_unchanged(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="traf_fail")
    shares_before = _share_map(company)
    mock_keitaro.fail_disable = AppError(
        502, "keitaro_bad_gateway", "disable failed"
    )

    resp = await client.post(
        f"/companies/{company['id']}/disable",
        headers=auth_headers,
        json={"expected_version": company["version"]},
    )
    assert resp.status_code == 502

    card = await client.get(f"/companies/{company['id']}", headers=auth_headers)
    assert card.status_code == 200
    body = card.json()
    assert body["traffic_status"] == "active"
    assert body["version"] == company["version"]
    assert _share_map(body) == shares_before


@pytest.mark.asyncio
async def test_enable_after_disable(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="traf_en")
    disabled = await client.post(
        f"/companies/{company['id']}/disable",
        headers=auth_headers,
        json={"expected_version": company["version"]},
    )
    assert disabled.status_code == 200
    shares = _share_map(disabled.json())

    enabled = await client.post(
        f"/companies/{company['id']}/enable",
        headers=auth_headers,
        json={"expected_version": disabled.json()["version"]},
    )
    assert enabled.status_code == 200, enabled.text
    assert mock_keitaro.calls["enable"] == 1
    assert enabled.json()["traffic_status"] == "active"
    assert _share_map(enabled.json()) == shares
