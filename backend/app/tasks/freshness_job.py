"""
Nightly freshness job for checking and refreshing data sources.
"""

import logging
from typing import List

from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis, CacheService
from app.connectors.socrata import SocrataConnector
from app.connectors.arcgis import ArcGISConnector
from app.services.data_catalog import DataCatalogService
from app.jobs.data_ingestion import DataIngestionJob
from app.utils.notifications import NotificationService

logger = logging.getLogger(__name__)


class FreshnessJob:
    """
    Nightly job to check data freshness and trigger re-ingestion.
    """

    async def run(self):
        """Execute freshness check and conditional ingestion."""
        logger.info("Starting nightly freshness job")

        async with AsyncSessionLocal() as db:
            redis = await get_redis()
            cache_service = CacheService(redis)
            socrata = SocrataConnector(cache_service)
            arcgis = ArcGISConnector(cache_service)

            try:
                catalog_service = DataCatalogService(db, socrata, arcgis)
                ingestion_job = DataIngestionJob(db, socrata, arcgis, catalog_service)

                # Get all registered sources
                sources = await catalog_service.get_all_sources()

                sources_to_refresh: List[str] = []

                # Check each source
                for source in sources:
                    logger.info(f"Checking freshness: {source.source_name}")

                    freshness = await catalog_service.check_freshness(
                        source.source_name
                    )

                    if freshness.get("needs_refresh"):
                        logger.info(
                            f"Source needs refresh: {source.source_name} "
                            f"(remote updated: {freshness.get('remote_updated_at')})"
                        )
                        sources_to_refresh.append(source.source_name)
                    else:
                        logger.info(f"Source is fresh: {source.source_name}")

                # Trigger ingestion for stale sources
                if sources_to_refresh:
                    logger.info(f"Re-ingesting {len(sources_to_refresh)} stale sources")

                    # Map source names to ingestion methods
                    ingestion_map = {
                        "ebr_property_info": ingestion_job.ingest_property_info,
                        "ebr_zoning": ingestion_job.ingest_zoning,
                        "ebr_311": ingestion_job.ingest_311_requests,
                    }

                    for source_name in sources_to_refresh:
                        method = ingestion_map.get(source_name)
                        if method:
                            try:
                                await method()
                                logger.info(f"Successfully re-ingested: {source_name}")
                            except Exception as e:
                                logger.error(f"Failed to re-ingest {source_name}: {e}")
                        else:
                            logger.warning(f"No ingestion method for: {source_name}")
                else:
                    logger.info("All sources are fresh, no ingestion needed")

                # Generate health report
                health = await catalog_service.get_health_summary()
                logger.info(f"Data health: {health}")

                # Send alerts if any sources are degraded/failed
                if health["degraded"] > 0 or health["failed"] > 0:
                    await self._send_alert(health)

            finally:
                await socrata.close()
                await arcgis.close()

        logger.info("Nightly freshness job completed")

    async def _send_alert(self, health_summary: dict):
        """Send alert for degraded/failed sources."""
        try:
            await NotificationService.notify_data_health_degraded(health_summary)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to send data health notification: %s", exc)
        finally:
            logger.warning(
                "Data health alert: %s degraded, %s failed sources",
                health_summary.get("degraded", 0),
                health_summary.get("failed", 0),
            )


async def run_freshness_job():
    """Entry point for scheduled job."""
    job = FreshnessJob()
    await job.run()


# For Celery integration
# @celery_app.task
# def nightly_freshness_check():
#     asyncio.run(run_freshness_job())
