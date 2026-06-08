from __future__ import annotations

from typing import Any, Optional

import httpx

from .models import DataSource


class CelesTrakClient:
    ACTIVE_GP_JSON_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json"

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None, timeout_seconds: float = 20.0):
        self._http_client = http_client
        self._timeout_seconds = timeout_seconds

    @classmethod
    def source(cls) -> DataSource:
        return DataSource(name="CelesTrak GP active", url=cls.ACTIVE_GP_JSON_URL)

    async def fetch_active_gp_records(self) -> list[dict[str, Any]]:
        """Fetch raw public active-satellite GP records from CelesTrak."""

        if self._http_client is not None:
            return await self._fetch_with(self._http_client)

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as http_client:
            return await self._fetch_with(http_client)

    async def _fetch_with(self, http_client: httpx.AsyncClient) -> list[dict[str, Any]]:
        response = await http_client.get(
            self.ACTIVE_GP_JSON_URL,
            headers={"User-Agent": "mission-ops-lite/0.1 (+public orbit data ingestion)"},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("CelesTrak active GP JSON response must be a list")
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("CelesTrak active GP JSON items must be objects")
        return payload
