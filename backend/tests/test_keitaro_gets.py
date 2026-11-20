"""Unit tests for HttpKeitaroClient GET parsing and error mapping.

Uses httpx.MockTransport only — never a real Keitaro server.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.clients.keitaro import (
    CAMPAIGN_PAGE_SIZE,
    KEITARO_NOT_FOUND,
    HttpKeitaroClient,
    _as_list,
    _map_keitaro_http_error,
    _normalize_admin_api_base,
    _parse_filter_payload,
)
from app.errors import AppError


def _client_with_handler(handler) -> HttpKeitaroClient:
    transport = httpx.MockTransport(handler)
    client = HttpKeitaroClient(
        base_url="http://keitaro.test",
        api_key="test-key",
        domain_name="d",
        group_name="g",
        source_name="s",
    )
    # Replace httpx client to use mock transport (same base path).
    client._client = httpx.AsyncClient(
        base_url="http://keitaro.test/admin_api/v1",
        headers={"Api-Key": "test-key", "Accept": "application/json"},
        transport=transport,
        timeout=httpx.Timeout(5.0),
    )
    return client


def test_as_list_normalizes_wrappers() -> None:
    assert _as_list(None) == []
    assert _as_list([1, 2]) == [1, 2]
    assert _as_list({"rows": [{"id": 1}]}) == [{"id": 1}]
    assert _as_list({"data": [{"id": 2}]}) == [{"id": 2}]
    assert _as_list({"id": 9, "name": "x"}) == [{"id": 9, "name": "x"}]
    assert _as_list("nope") == []


def test_parse_filter_payload_csv_and_json_array_string() -> None:
    assert _parse_filter_payload(None) == []
    assert _parse_filter_payload(["DE", " AT "]) == ["DE", "AT"]
    assert _parse_filter_payload("DE,AT, PL") == ["DE", "AT", "PL"]
    assert _parse_filter_payload('["DE","AT"]') == ["DE", "AT"]
    assert _parse_filter_payload("[]") == []
    assert _parse_filter_payload("") == []


def test_map_keitaro_http_error_404_distinguishable() -> None:
    response = httpx.Response(404, json={"error": "Campaign not found"})
    err = _map_keitaro_http_error(response)
    assert isinstance(err, AppError)
    assert err.error == KEITARO_NOT_FOUND
    assert err.status_code == 409
    assert "Campaign not found" in err.message


def test_map_keitaro_http_error_5xx_body() -> None:
    response = httpx.Response(500, json={"error": "boom"})
    err = _map_keitaro_http_error(response)
    assert err.error == "keitaro_bad_gateway"
    assert err.message == "boom"


@pytest.mark.asyncio
async def test_get_offer_404_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/offers/999")
        return httpx.Response(404, json={"error": "Offer not found"})

    client = _client_with_handler(handler)
    try:
        assert await client.get_offer(999) is None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_offer_5xx_raises_502() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    client = _client_with_handler(handler)
    try:
        with pytest.raises(AppError) as ei:
            await client.get_offer(1)
        assert ei.value.error == "keitaro_bad_gateway"
        assert ei.value.status_code == 502
        assert "unavailable" in ei.value.message
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_campaign_parses_filters_and_offer_stream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/campaigns/10"):
            return httpx.Response(
                200, json={"id": 10, "name": "Acme", "state": "active"}
            )
        if path.endswith("/campaigns/10/streams"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "google",
                        "position": 1,
                        "schema": "action",
                        "action_type": "http",
                        "action_payload": "https://google.com",
                        "filters": [
                            {
                                "name": "country",
                                "mode": "accept",
                                "payload": '["DE","AT"]',
                            }
                        ],
                        "offers": [],
                    },
                    {
                        "id": 2,
                        "name": "offers",
                        # API enum is landings|redirect|action — not "offers".
                        "schema": "landings",
                        "position": 2,
                        "filters": [],
                        "offers": [
                            {"offer_id": 3749, "share": 70, "state": "active"},
                            {"offer_id": 3801, "share": 30, "state": "active"},
                        ],
                    },
                ],
            )
        return httpx.Response(500, json={"error": f"unexpected {path}"})

    client = _client_with_handler(handler)
    try:
        camp = await client.get_campaign(10)
        assert camp is not None
        assert camp.campaign_id == 10
        assert camp.name == "Acme"
        assert len(camp.streams) == 2

        google = camp.streams[0]
        assert google.schema == "action"
        assert google.filters_geo == ["DE", "AT"]

        offers = camp.streams[1]
        assert offers.schema == "landings"  # not rewritten to "offers"
        assert offers.name == "offers"
        assert [(o.offer_id, o.share) for o in offers.offers] == [
            (3749, 70),
            (3801, 30),
        ]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_campaign_404_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = _client_with_handler(handler)
    try:
        assert await client.get_campaign(404) is None
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_find_campaign_by_name_paginates() -> None:
    calls: list[tuple[str | None, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/campaigns") and request.method == "GET":
            limit = request.url.params.get("limit")
            offset = request.url.params.get("offset")
            calls.append((limit, offset))
            off = int(offset or 0)
            if off == 0:
                page = [
                    {"id": i, "name": f"c{i}"} for i in range(1, CAMPAIGN_PAGE_SIZE + 1)
                ]
                return httpx.Response(200, json=page)
            if off == CAMPAIGN_PAGE_SIZE:
                return httpx.Response(
                    200, json=[{"id": 999, "name": "Target Co"}]
                )
            return httpx.Response(200, json=[])
        if path.endswith("/campaigns/999"):
            return httpx.Response(
                200, json={"id": 999, "name": "Target Co", "state": "disabled"}
            )
        if path.endswith("/campaigns/999/streams"):
            return httpx.Response(200, json=[])
        return httpx.Response(500, json={"error": f"unexpected {path}"})

    client = _client_with_handler(handler)
    try:
        camp = await client.find_campaign_by_name("target co")
        assert camp is not None
        assert camp.campaign_id == 999
        assert camp.state == "disabled"
        assert calls[0] == (str(CAMPAIGN_PAGE_SIZE), "0")
        assert calls[1] == (str(CAMPAIGN_PAGE_SIZE), str(CAMPAIGN_PAGE_SIZE))
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_list_offers_uses_as_list_and_filter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/offers")
        return httpx.Response(
            200,
            json={
                "rows": [
                    {"id": 1, "name": "Alpha", "country": ["MX", "US"]},
                    {"id": 2, "name": "Beta", "country": ["DE"]},
                ]
            },
        )

    client = _client_with_handler(handler)
    try:
        items = await client.list_offers(q="alp")
        assert len(items) == 1
        assert items[0].offer_id == 1
        assert items[0].country == ["MX", "US"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_get_retries_on_5xx_then_succeeds() -> None:
    hits = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        hits["n"] += 1
        if hits["n"] < 3:
            return httpx.Response(502, json={"error": "temp"})
        return httpx.Response(200, json={"id": 5, "name": "Ok"})

    client = _client_with_handler(handler)
    try:
        offer = await client.get_offer(5)
        assert offer is not None
        assert offer.name == "Ok"
        assert hits["n"] == 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_parse_stream_csv_payload_and_legacy_percent() -> None:
    client = HttpKeitaroClient(
        base_url="http://keitaro.test",
        api_key="k",
        domain_name="d",
        group_name="g",
        source_name="s",
    )
    try:
        stream = client._parse_stream(
            {
                "id": 3,
                "name": "google",
                "position": 1,
                "schema": "action",
                "filters": [{"name": "country", "payload": "US,CA"}],
                "offers": [{"id": 11, "percent": 100}],
            }
        )
        assert stream.filters_geo == ["US", "CA"]
        assert stream.offers[0].offer_id == 11
        assert stream.offers[0].share == 100
        # object action_payload → JSON string
        stream2 = client._parse_stream(
            {
                "id": 4,
                "name": "x",
                "schema": "action",
                "action_payload": {"url": "https://x"},
                "filters": [],
                "offers": [],
            }
        )
        assert json.loads(stream2.action_payload or "") == {"url": "https://x"}
    finally:
        await client.aclose()


def test_normalize_admin_api_base() -> None:
    assert (
        _normalize_admin_api_base("https://tlgk.host:8105")
        == "https://tlgk.host:8105/admin_api/v1"
    )
    assert (
        _normalize_admin_api_base("https://tlgk.host:8105/v1")
        == "https://tlgk.host:8105/admin_api/v1"
    )
    assert (
        _normalize_admin_api_base("https://tlgk.host:8105/admin_api/v1/")
        == "https://tlgk.host:8105/admin_api/v1"
    )


@pytest.mark.asyncio
async def test_update_google_geo_puts_streams_id() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"id": 1328656})

    client = _client_with_handler(handler)
    try:
        await client.update_google_geo(
            campaign_id=215957,
            stream_id=1328656,
            geo_codes=["MX", "US"],
        )
        assert seen["method"] == "PUT"
        assert seen["path"].endswith("/streams/1328656")
        assert "/campaigns/" not in str(seen["path"])
        body = seen["body"]
        assert isinstance(body, dict)
        assert body["campaign_id"] == 215957
        assert body["filters"] == [
            {"name": "country", "mode": "accept", "payload": ["MX", "US"]}
        ]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_update_stream_offers_puts_streams_id() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"id": 1})

    client = _client_with_handler(handler)
    try:
        await client.update_stream_offers(
            campaign_id=10,
            stream_id=99,
            offers=[(3749, 100)],
        )
        assert seen["path"].endswith("/streams/99")
        body = seen["body"]
        assert isinstance(body, dict)
        assert body["campaign_id"] == 10
        assert body["offers"] == [
            {"offer_id": 3749, "share": 100, "state": "active"}
        ]
    finally:
        await client.aclose()
