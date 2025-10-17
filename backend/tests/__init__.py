"""Test package initialization."""

import os

# Default settings to satisfy app.core.config.Settings requirements for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://gallagher:test_password@localhost:5432/gallagher_mhp_test",
)

