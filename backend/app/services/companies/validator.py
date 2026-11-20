from __future__ import annotations

import re

from app.errors import AppError
from app.repositories import GeoRepository

NAME_PREFIX = "test_yasinsky_company"
NAME_RE = re.compile(r"^[a-zA-Z0-9_\- ]{1,64}$")
GEO_RE = re.compile(r"^[A-Z]{2}$")


class CompanyValidator:
    def __init__(self, geos: GeoRepository) -> None:
        self._geos = geos

    async def geo_codes(self, codes: list[str]) -> list[str]:
        if not codes:
            raise AppError(
                422,
                "validation_error",
                "geo_codes must not be empty.",
                fields={"geo_codes": "Add at least one geo code."},
            )
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in codes:
            code = raw.strip().upper()
            if not GEO_RE.fullmatch(code):
                raise AppError(
                    422,
                    "validation_error",
                    "Invalid geo code.",
                    fields={"geo_codes": "Use 2-letter codes from the geo list."},
                )
            if code in seen:
                raise AppError(
                    422,
                    "validation_error",
                    "Duplicate geo code.",
                    fields={"geo_codes": f"{code} is listed more than once."},
                )
            seen.add(code)
            normalized.append(code)
        await self.known_geo_codes(normalized)
        return normalized

    async def known_geo_codes(self, codes: list[str]) -> None:
        found = {g.code for g in await self._geos.get_by_codes(codes)}
        unknown = [c for c in codes if c not in found]
        if unknown:
            raise AppError(
                422,
                "unknown_geo",
                f"Unknown geo codes: {', '.join(unknown)}",
                fields={"geo_codes": "Unknown geo code."},
            )

    @staticmethod
    def offer_id(offer_id: int) -> None:
        if offer_id < 1:
            raise AppError(
                422,
                "validation_error",
                "offer_id is required.",
                fields={"offer_id": "Pick an offer."},
            )

    @staticmethod
    def name(name: str) -> None:
        if name != name.strip():
            raise AppError(
                422,
                "validation_error",
                "Name must not have leading/trailing spaces.",
                fields={"name": "Invalid name."},
            )
        if not NAME_RE.fullmatch(name) or not name.startswith(NAME_PREFIX):
            raise AppError(
                422,
                "validation_error",
                "Invalid company name.",
                fields={
                    "name": "Must start with test_yasinsky_company. 1-64 chars: letters, digits, _ - space."
                },
            )
