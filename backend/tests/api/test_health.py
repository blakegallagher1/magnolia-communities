"""
Tests for health endpoints.
"""

import pytest

from app.main import app
from app.core.database import get_db
from app.core.redis import get_redis


@pytest.mark.asyncio
async def test_liveness_endpoint(api_client):
    response = await api_client.get("/api/v1/health/liveness")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_readiness_healthy(api_client):
    response = await api_client.get("/api/v1/health/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["database"]["status"] == "pass"
    assert payload["checks"]["redis"]["status"] == "pass"


@pytest.mark.asyncio
async def test_readiness_database_failure(api_client):
    class FailingSession:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("database timeout")

        async def close(self):
            return None

    async def failing_db():
        session = FailingSession()
        try:
            yield session
        finally:
            await session.close()

    original = app.dependency_overrides.get(get_db, getattr(app.state, "test_db_override", None))
    app.dependency_overrides[get_db] = failing_db
    try:
        response = await api_client.get("/api/v1/health/readiness")
    finally:
        if original:
            app.dependency_overrides[get_db] = original
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["database"]["status"] == "fail"


@pytest.mark.asyncio
async def test_readiness_redis_failure(api_client):
    class FailingRedis:
        async def ping(self):
            raise RuntimeError("redis unreachable")

    async def failing_redis():
        return FailingRedis()

    original = app.dependency_overrides.get(get_redis, getattr(app.state, "test_redis_override", None))
    app.dependency_overrides[get_redis] = failing_redis
    try:
        response = await api_client.get("/api/v1/health/readiness")
    finally:
        if original:
            app.dependency_overrides[get_redis] = original
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["redis"]["status"] == "fail"
