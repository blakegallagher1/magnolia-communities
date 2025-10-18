"""Tests for application bootstrap helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bootstrap import DEFAULT_DATA_SOURCES, seed_data_catalog


@pytest.mark.asyncio
async def test_seed_data_catalog_inserts_missing_entries():
    session = AsyncMock()
    result_missing = MagicMock()
    result_missing.scalar_one_or_none.return_value = None
    session.execute.side_effect = [result_missing for _ in DEFAULT_DATA_SOURCES]
    session.add = MagicMock()

    await seed_data_catalog(session=session)

    assert session.add.call_count == len(DEFAULT_DATA_SOURCES)
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_seed_data_catalog_skips_existing_entries():
    session = AsyncMock()
    existing_row = object()
    result_existing = MagicMock()
    result_existing.scalar_one_or_none.return_value = existing_row
    session.execute.side_effect = [result_existing for _ in DEFAULT_DATA_SOURCES]

    await seed_data_catalog(session=session)

    session.add.assert_not_called()
    session.commit.assert_awaited()
