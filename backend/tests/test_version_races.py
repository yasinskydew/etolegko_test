"""Optimistic lock races on parallel mutations."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from tests.conftest import create_ready_company, offers_stream


@pytest.mark.asyncio
async def test_parallel_actions_same_version_one_conflicts(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    company = await create_ready_company(client, auth_headers, name="test_yasinsky_company_race")
    cid = company["id"]
    stream_id = offers_stream(company)["id"]
    version = company["version"]

    async def add_offer(offer_id: int) -> int:
        resp = await client.post(
            f"/companies/{cid}/streams/{stream_id}/actions",
            headers=auth_headers,
            json={
                "action": "add",
                "offer_id": offer_id,
                "expected_version": version,
            },
        )
        return resp.status_code

    # Two concurrent adds with the same expected_version; FOR UPDATE + version check.
    statuses = await asyncio.gather(add_offer(3801), add_offer(3900))
    assert sorted(statuses) == [200, 409]
