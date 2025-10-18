"""
Metrics instrumentation tests.
"""

import pytest
from prometheus_client import REGISTRY

from fastapi import Response

from app.core.metrics import record_external_api_retry
from app.core.redis import CacheService
from app.main import app


@app.get("/__test-error")
async def trigger_error():
    return Response(status_code=500)


def _get_metric_value(metric: str, labels: dict) -> float:
    value = REGISTRY.get_sample_value(metric, labels)
    return value or 0.0


@pytest.mark.asyncio
async def test_http_metrics_and_request_id(api_client):
    labels = {"method": "GET", "path": "/api/v1/health/liveness", "status": "200"}
    before = _get_metric_value("app_http_requests_total", labels)

    response = await api_client.get("/api/v1/health/liveness")

    after = _get_metric_value("app_http_requests_total", labels)
    assert after == pytest.approx(before + 1)
    assert "X-Request-ID" in response.headers
    assert response.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_http_error_metrics(api_client):
    total_labels = {"method": "GET", "path": "/__test-error", "status": "500"}
    error_labels = total_labels.copy()

    total_before = _get_metric_value("app_http_requests_total", total_labels)
    errors_before = _get_metric_value("app_http_request_errors_total", error_labels)

    response = await api_client.get("/__test-error")

    total_after = _get_metric_value("app_http_requests_total", total_labels)
    errors_after = _get_metric_value("app_http_request_errors_total", error_labels)

    assert response.status_code == 500
    assert total_after == pytest.approx(total_before + 1)
    assert errors_after == pytest.approx(errors_before + 1)


class InMemoryRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value
        return True

    async def delete(self, key):
        return 1 if key in self.store else 0

    async def exists(self, key):
        return 1 if key in self.store else 0

    async def scan_iter(self, match):
        for key in list(self.store):
            if match == "*" or key.startswith(match.rstrip("*")):
                yield key


@pytest.mark.asyncio
async def test_cache_metrics():
    cache = CacheService(InMemoryRedis())

    miss_before = _get_metric_value("app_cache_operations_total", {"operation": "miss"})
    await cache.get("missing")
    miss_after = _get_metric_value("app_cache_operations_total", {"operation": "miss"})
    assert miss_after == pytest.approx(miss_before + 1)

    set_before = _get_metric_value("app_cache_operations_total", {"operation": "set"})
    await cache.set("key", {"value": 1})
    set_after = _get_metric_value("app_cache_operations_total", {"operation": "set"})
    assert set_after == pytest.approx(set_before + 1)

    hit_before = _get_metric_value("app_cache_operations_total", {"operation": "hit"})
    await cache.get("key")
    hit_after = _get_metric_value("app_cache_operations_total", {"operation": "hit"})
    assert hit_after == pytest.approx(hit_before + 1)

    exists_before = _get_metric_value(
        "app_cache_operations_total", {"operation": "exists"}
    )
    await cache.exists("key")
    exists_after = _get_metric_value(
        "app_cache_operations_total", {"operation": "exists"}
    )
    assert exists_after == pytest.approx(exists_before + 1)

    delete_before = _get_metric_value(
        "app_cache_operations_total", {"operation": "delete"}
    )
    await cache.delete("key")
    delete_after = _get_metric_value(
        "app_cache_operations_total", {"operation": "delete"}
    )
    assert delete_after == pytest.approx(delete_before + 1)

    await cache.set("another", {"value": 2})
    invalidate_before = _get_metric_value(
        "app_cache_operations_total", {"operation": "invalidate"}
    )
    await cache.invalidate_pattern("an*")
    invalidate_after = _get_metric_value(
        "app_cache_operations_total", {"operation": "invalidate"}
    )
    assert invalidate_after == pytest.approx(invalidate_before + 1)


def test_external_api_retry_metric():
    before = _get_metric_value(
        "app_external_api_retries_total", {"service": "test-service"}
    )
    record_external_api_retry("test-service")
    after = _get_metric_value(
        "app_external_api_retries_total", {"service": "test-service"}
    )
    assert after == pytest.approx(before + 1)
