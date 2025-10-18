"""
Pytest configuration and fixtures.
"""
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an AsyncSession mock for service logic tests."""
    async with AsyncSession() as session:  # type: ignore[call-arg]
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def api_client(monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    """HTTPX AsyncClient configured against the FastAPI app with test overrides."""
    from app.main import app
    from app.core.database import get_db
    from app.core.redis import get_redis

    class StubResult:
        def scalar(self):
            return 1

        def scalar_one(self):
            return 1

    class StubSession:
        async def execute(self, *_args, **_kwargs):
            return StubResult()

        async def close(self):
            return None

    class StubRedis:
        async def ping(self):
            return True

    async def override_db():
        session = StubSession()
        try:
            yield session
        finally:
            await session.close()

    async def override_redis():
        return StubRedis()

    async def _init_db_stub():
        return None

    monkeypatch.setattr("app.main.init_db", _init_db_stub)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    app.state.test_db_override = override_db
    app.state.test_redis_override = override_redis

    await app.router.startup()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        await app.router.shutdown()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis, None)
        if hasattr(app.state, "test_db_override"):
            delattr(app.state, "test_db_override")
        if hasattr(app.state, "test_redis_override"):
            delattr(app.state, "test_redis_override")
