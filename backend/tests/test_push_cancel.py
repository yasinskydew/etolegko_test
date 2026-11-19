"""Push idempotency / failure leaves update mode; Cancel restores snapshot."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.errors import AppError
from tests.conftest import MockKeitaroClient, create_ready_company, offers_stream


@pytest.mark.asyncio
async def test_push_idempotent_and_keeps_removed_archive(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="push_idem")
    cid = company["id"]
    stream_id = offers_stream(company)["id"]
    version = company["version"]

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
        json={"action": "remove", "offer_id": 3801, "expected_version": version},
    )
    assert r.status_code == 200, r.text
    assert offers_stream(r.json())["sync"] == "update_mode"

    first = await client.post(f"/companies/{cid}/sync", headers=auth_headers)
    assert first.status_code == 200, first.text
    body = first.json()
    assert offers_stream(body)["sync"] == "synced"
    removed = [
        o for o in offers_stream(body)["offers"] if o["offer_id"] == 3801
    ]
    assert len(removed) == 1
    assert removed[0]["removed"] is True

    calls_before = mock_keitaro.calls["update_stream_offers"]
    second = await client.post(f"/companies/{cid}/sync", headers=auth_headers)
    assert second.status_code == 200, second.text
    assert mock_keitaro.calls["update_stream_offers"] == calls_before + 1
    again = [
        o for o in offers_stream(second.json())["offers"] if o["offer_id"] == 3801
    ]
    assert len(again) == 1 and again[0]["removed"] is True
    assert offers_stream(second.json())["sync"] == "synced"


@pytest.mark.asyncio
async def test_push_keitaro_failure_keeps_update_mode_and_old_snapshot(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="push_fail")
    cid = company["id"]
    stream_id = offers_stream(company)["id"]
    version = company["version"]
    before_offers = offers_stream(company)["offers"]

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "add", "offer_id": 3801, "expected_version": version},
    )
    assert r.status_code == 200, r.text
    assert offers_stream(r.json())["sync"] == "update_mode"
    working_after_edit = offers_stream(r.json())["offers"]

    mock_keitaro.fail_update_offers = AppError(
        502, "keitaro_bad_gateway", "push failed"
    )
    fail = await client.post(f"/companies/{cid}/sync", headers=auth_headers)
    assert fail.status_code == 502

    card = await client.get(f"/companies/{cid}", headers=auth_headers)
    assert card.status_code == 200
    stream = offers_stream(card.json())
    assert stream["sync"] == "update_mode"
    assert {(o["offer_id"], o["removed"], o["percent"]) for o in stream["offers"]} == {
        (o["offer_id"], o["removed"], o["percent"]) for o in working_after_edit
    }

    # Cancel restores original snapshot (single offer 100%) — proves snapshot untouched.
    cancel = await client.post(f"/companies/{cid}/cancel", headers=auth_headers)
    assert cancel.status_code == 200, cancel.text
    restored = offers_stream(cancel.json())
    assert restored["sync"] == "synced"
    assert {(o["offer_id"], o["percent"], o["removed"]) for o in restored["offers"]} == {
        (o["offer_id"], o["percent"], o["removed"]) for o in before_offers
    }


@pytest.mark.asyncio
async def test_cancel_restores_snapshot_without_keitaro(
    client: AsyncClient,
    auth_headers: dict[str, str],
    mock_keitaro: MockKeitaroClient,
) -> None:
    company = await create_ready_company(client, auth_headers, name="cancel_ok")
    cid = company["id"]
    stream_id = offers_stream(company)["id"]
    snapshot = offers_stream(company)["offers"]
    version = company["version"]

    r = await client.post(
        f"/companies/{cid}/streams/{stream_id}/actions",
        headers=auth_headers,
        json={"action": "add", "offer_id": 3801, "expected_version": version},
    )
    assert r.status_code == 200

    mutating = ("create", "delete", "update_stream_offers", "enable", "disable", "update_google_geo")
    before = {k: mock_keitaro.calls[k] for k in mutating}
    cancel = await client.post(f"/companies/{cid}/cancel", headers=auth_headers)
    assert cancel.status_code == 200, cancel.text
    assert {k: mock_keitaro.calls[k] for k in mutating} == before

    restored = offers_stream(cancel.json())
    assert restored["sync"] == "synced"
    assert {(o["offer_id"], o["percent"], o["removed"], o["pinned"]) for o in restored["offers"]} == {
        (o["offer_id"], o["percent"], o["removed"], o["pinned"]) for o in snapshot
    }
