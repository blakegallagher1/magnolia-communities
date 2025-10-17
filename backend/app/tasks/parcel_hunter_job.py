"""Background job for running Parcel Hunter on schedule."""

import logging

from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis, CacheService
from app.connectors.socrata import SocrataConnector
from app.connectors.arcgis import ArcGISConnector
from app.services.parcel_hunter import ParcelHunterService, ParcelHunterConfig

logger = logging.getLogger(__name__)


async def run_parcel_hunter_job():
    """Run the Parcel Hunter workflow."""
    async with AsyncSessionLocal() as db:
        redis = await get_redis()
        cache = CacheService(redis)
        socrata = SocrataConnector(cache)
        arcgis = ArcGISConnector(cache)

        service = ParcelHunterService(db, socrata, arcgis, ParcelHunterConfig())
        run = await service.run()
        logger.info(
            "Parcel Hunter scheduled run completed id=%s status=%s candidates=%s leads=%s",
            run.id,
            run.status,
            run.total_candidates,
            run.leads_created,
        )
