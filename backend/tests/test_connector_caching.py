"""Tests for connector caching behaviour."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.connectors.arcgis import ArcGISConnector, ArcGISService
from app.connectors.socrata import SocrataConnector
from app.core.config import settings


class FakeCache:
    """In-memory cache stub for testing."""

    def __init__(self, initial: dict[str, Any] | None = None):
        self.store = initial or {}
        self.set_calls: list[tuple[str, Any, int]] = []

    async def get(self, key: str) -> Any:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ttl: int) -> bool:
        self.store[key] = value
        self.set_calls.append((key, value, ttl))
        return True


class DummyResponse:
    def __init__(self, payload: Any):
        self._payload = payload

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        return None


@pytest.mark.asyncio
async def test_socrata_cache_hit(monkeypatch):
    cache = FakeCache()
    connector = SocrataConnector(cache)
    connector.client = AsyncMock()
    key = connector._build_cache_key("dataset", select=["b", "a"], limit=10, offset=0)
    cache.store[key] = [{"id": 1}]

    result = await connector.query("dataset", select=["a", "b"], limit=10, offset=0)

    assert result == [{"id": 1}]
    connector.client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_socrata_cache_miss_sets_with_ttl(monkeypatch):
    cache = FakeCache()
    connector = SocrataConnector(cache)
    response_data = [{"id": 2}]
    connector.client = AsyncMock()
    connector.client.get = AsyncMock(return_value=DummyResponse(response_data))
    connector.client.aclose = AsyncMock()

    monkeypatch.setattr(settings, "SOCRATA_CACHE_TTL", 42)

    result = await connector.query("dataset", select=["x"], offset=0)

    assert result == response_data
    assert cache.set_calls[0][2] == 42
    connector.client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_arcgis_cache_hit(monkeypatch):
    cache = FakeCache()
    connector = ArcGISConnector(cache)
    connector.client = AsyncMock()
    key = connector._build_cache_key(
        ArcGISService.TAX_PARCEL,
        where="parcel='1'",
        out_fields=["parcel", "owner"],
    )
    cache.store[key] = {"features": []}

    result = await connector.query(
        ArcGISService.TAX_PARCEL,
        where="parcel='1'",
        out_fields=["owner", "parcel"],
    )

    assert result == {"features": []}


@pytest.mark.asyncio
async def test_arcgis_cache_miss_sets_with_ttl(monkeypatch):
    cache = FakeCache()
    connector = ArcGISConnector(cache)
    payload = {"features": [1]}
    connector.client = AsyncMock()
    connector.client.get = AsyncMock(return_value=DummyResponse(payload))
    connector.client.aclose = AsyncMock()

    monkeypatch.setattr(settings, "ARCGIS_CACHE_TTL", 99)

    result = await connector.query(ArcGISService.ZONING, where="1=1")

    assert result == payload
    assert cache.set_calls[0][2] == 99
    connector.client.get.assert_awaited_once()
