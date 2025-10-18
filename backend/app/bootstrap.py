"""
Application bootstrap helpers (runs during startup).
"""

from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.arcgis import ArcGISService
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.data_catalog import DataCatalog, DataSourceType

logger = logging.getLogger(__name__)


DEFAULT_DATA_SOURCES = (
    {
        "source_name": "ebr_property_info",
        "source_type": DataSourceType.SOCRATA,
        "dataset_id": settings.SOCRATA_PROPERTY_DATASET,
        "endpoint": f"{settings.SOCRATA_BASE_URL}/{settings.SOCRATA_PROPERTY_DATASET}.json",
        "metadata": {"description": "East Baton Rouge parcel master (Socrata)"},
    },
    {
        "source_name": "ebr_zoning",
        "source_type": DataSourceType.ARCGIS,
        "dataset_id": ArcGISService.ZONING.value,
        "endpoint": f"{settings.ARCGIS_BASE_URL}/{ArcGISService.ZONING.value}",
        "metadata": {"description": "Zoning districts (ArcGIS)"},
    },
    {
        "source_name": "ebr_311",
        "source_type": DataSourceType.ARCGIS,
        "dataset_id": ArcGISService.SR_311_OPEN.value,
        "endpoint": f"{settings.ARCGIS_311_BASE_URL}/{ArcGISService.SR_311_OPEN.value}",
        "metadata": {"description": "311 service requests (ArcGIS FeatureServer)"},
    },
)


async def _ensure_sources(session: AsyncSession, defaults: Iterable[dict]) -> None:
    """Insert default catalog sources if they are missing."""
    for config in defaults:
        stmt = select(DataCatalog).where(DataCatalog.source_name == config["source_name"])
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            continue

        entry = DataCatalog(
            source_type=config["source_type"],
            source_name=config["source_name"],
            dataset_id=config["dataset_id"],
            endpoint=config["endpoint"],
            extra_metadata=config.get("metadata") or {},
        )
        session.add(entry)
        logger.info("Seeded data catalog entry for %s", config["source_name"])


async def seed_data_catalog(session: AsyncSession | None = None) -> None:
    """
    Ensure baseline data catalog entries exist.

    If a session is not provided, a temporary AsyncSession will be created.
    """
    owns_session = session is None
    if owns_session:
        async with AsyncSessionLocal() as temp_session:
            await _ensure_sources(temp_session, DEFAULT_DATA_SOURCES)
            await temp_session.commit()
        return

    await _ensure_sources(session, DEFAULT_DATA_SOURCES)
    await session.commit()
