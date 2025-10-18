"""Rate limiting integration tests."""

import uuid

import pytest
from fastapi import Request

from slowapi.util import get_remote_address

from app.core.rate_limiter import limiter
from app.main import app


def _test_key_func(request: Request) -> str:
    return request.headers.get("x-test-key", get_remote_address(request))


@app.post("/__limited")
@limiter.limit("3/minute", key_func=_test_key_func)
async def limited_endpoint(request: Request):  # pragma: no cover - exercised via tests
    return {"ok": True}


shared_global = limiter.shared_limit("5/minute", scope="global-test")


@app.get("/__global")
@shared_global
async def global_endpoint(request: Request):  # pragma: no cover - exercised via tests
    return {"ok": True}


@pytest.mark.asyncio
async def test_per_endpoint_rate_limit(api_client):
    from slowapi import extension as slowapi_extension

    assert slowapi_extension._rate_limit_exceeded_handler.__name__ == "_rate_limit_handler"
    limiter.reset()
    headers = {"x-test-key": f"per-test-{uuid.uuid4()}"}
    for _ in range(3):
        response = await api_client.post("/__limited", headers=headers)
        assert response.status_code == 200

    response = await api_client.post("/__limited", headers=headers)
    assert response.status_code == 429


@pytest.mark.asyncio
async def test_global_rate_limit(api_client):
    from slowapi import extension as slowapi_extension

    assert slowapi_extension._rate_limit_exceeded_handler.__name__ == "_rate_limit_handler"
    limiter.reset()

    unique_scope = f"global-test-{uuid.uuid4()}"
    path = f"/__global/{uuid.uuid4()}"
    decorator = limiter.shared_limit("5/minute", scope=unique_scope)

    @app.get(path)
    @decorator
    async def _dynamic_global(request: Request):  # pragma: no cover - test only
        return {"ok": True}

    headers = {"x-test-key": unique_scope}
    for _ in range(5):
        response = await api_client.get(path, headers=headers)
        assert response.status_code == 200

    response = await api_client.get(path, headers=headers)
    assert response.status_code == 429
