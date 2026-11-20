"""Single error contract: every non-2xx is ErrorBody {error, message, fields?}."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.errors import AppError, ErrorCode
from app.main import app
from app.services.companies import CompanyQueryService
from tests.conftest import MockKeitaroClient


def _assert_error_body(resp, status: int, code: str) -> dict:  # type: ignore[no-untyped-def]
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["error"] == code
    assert isinstance(body["message"], str) and body["message"]
    assert set(body) <= {"error", "message", "fields"}
    return body


@pytest.mark.asyncio
async def test_request_validation_is_422_error_body_with_fields(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post(
        "/companies",
        headers={**auth_headers, "Idempotency-Key": "k"},
        json={"geo_codes": [], "offer_id": 0},
    )
    body = _assert_error_body(resp, 422, "validation_error")
    assert {"name", "geo_codes", "offer_id"} <= set(body["fields"])

    resp = await client.get("/companies", headers=auth_headers, params={"page": 0})
    body = _assert_error_body(resp, 422, "validation_error")
    assert "page" in body["fields"]


@pytest.mark.asyncio
async def test_login_validation_and_unauthorized(client: AsyncClient) -> None:
    _assert_error_body(await client.post("/auth/login", json={}), 422, "validation_error")
    _assert_error_body(
        await client.post("/auth/login", json={"username": "admin", "password": "nope"}),
        401,
        "unauthorized",
    )
    _assert_error_body(await client.get("/companies"), 401, "unauthorized")


@pytest.mark.asyncio
async def test_unknown_route_and_method(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    _assert_error_body(await client.get("/nope", headers=auth_headers), 404, "not_found")
    _assert_error_body(
        await client.delete("/companies", headers=auth_headers), 405, "method_not_allowed"
    )
    _assert_error_body(await client.get("/companies/999", headers=auth_headers), 404, "not_found")


@pytest.mark.asyncio
async def test_unhandled_error_is_500_error_body(
    mock_keitaro: MockKeitaroClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(self: CompanyQueryService, company_id: int) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(CompanyQueryService, "get_company", boom)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/companies/1", headers=auth_headers)
    body = _assert_error_body(resp, 500, "internal_error")
    assert "boom" not in body["message"]


@pytest.mark.asyncio
async def test_create_sets_location_on_201_and_replay(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    body = {"name": "test_yasinsky_company_loc", "geo_codes": ["MX"], "offer_id": 3749}
    headers = {**auth_headers, "Idempotency-Key": "loc-key"}
    first = await client.post("/companies", headers=headers, json=body)
    assert first.status_code == 201
    assert first.headers["location"] == f"/companies/{first.json()['id']}"
    replay = await client.post("/companies", headers=headers, json=body)
    assert replay.status_code == 200
    assert replay.headers["location"] == first.headers["location"]


def test_app_error_rejects_wrong_status_for_code() -> None:
    with pytest.raises(ValueError):
        AppError(502, "name_taken", "x")
    with pytest.raises(ValueError):
        AppError(409, "no_such_code", "x")


def test_openapi_documents_error_body_everywhere() -> None:
    schema = app.openapi()
    components = schema["components"]["schemas"]
    assert "HTTPValidationError" not in components
    assert set(components["ErrorCode"]["enum"]) == {c.value for c in ErrorCode}
    for path, methods in schema["paths"].items():
        for method, op in methods.items():
            for status, resp in op["responses"].items():
                if status.startswith(("4", "5")):
                    ref = resp["content"]["application/json"]["schema"]["$ref"]
                    assert ref.endswith("/ErrorBody"), (path, method, status)
