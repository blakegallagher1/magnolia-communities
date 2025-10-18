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
    """HTTPX AsyncClient configured against the FastAPI app."""
    from app.main import app
    from app.core.database import get_db

    async def _init_db_stub():
        return None

    monkeypatch.setattr("app.main.init_db", _init_db_stub)

    async def override_db():
        yield None

    app.dependency_overrides[get_db] = override_db

    await app.router.startup()

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        await app.router.shutdown()
        app.dependency_overrides.pop(get_db, None)
