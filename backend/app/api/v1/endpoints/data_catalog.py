"""
Data catalog and freshness tracking endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.redis import get_redis, CacheService
from app.connectors.socrata import SocrataConnector
from app.connectors.arcgis import ArcGISConnector
from app.services.data_catalog import DataCatalogService

router = APIRouter()


class DataSourceStatus(BaseModel):
    """Data source status schema."""
    name: str
    status: str
    last_ingest: datetime | None
    row_count: int
    consecutive_failures: int


class DataHealthResponse(BaseModel):
    """Data health summary schema."""
    total_sources: int
    healthy: int
    degraded: int
    failed: int
    sources: List[DataSourceStatus]


@router.get("/health", response_model=DataHealthResponse)
async def get_data_health(
    db: AsyncSession = Depends(get_db),
):
    """
    Get overall data health summary.
    
    Returns status of all registered data sources including:
    - Total source count
    - Healthy/degraded/failed counts
    - Per-source status details
    """
    redis = await get_redis()
    cache_service = CacheService(redis)
    socrata = SocrataConnector(cache_service)
    arcgis = ArcGISConnector(cache_service)
    
    try:
        service = DataCatalogService(db, socrata, arcgis)
        summary = await service.get_health_summary()
        
        return summary
    finally:
        await socrata.close()
        await arcgis.close()


@router.post("/sources/{source_name}/check-freshness")
async def check_source_freshness(
    source_name: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Check if a data source needs refresh.
    
    Compares remote updated_at timestamp with local cache.
    Returns needs_refresh=True if remote is newer.
    """
    redis = await get_redis()
    cache_service = CacheService(redis)
    socrata = SocrataConnector(cache_service)
    arcgis = ArcGISConnector(cache_service)
    
    try:
        service = DataCatalogService(db, socrata, arcgis)
        freshness = await service.check_freshness(source_name)
        
        return freshness
    finally:
        await socrata.close()
        await arcgis.close()


@router.get("/sources")
async def list_data_sources(
    db: AsyncSession = Depends(get_db),
):
    """List all registered data sources."""
    redis = await get_redis()
    cache_service = CacheService(redis)
    socrata = SocrataConnector(cache_service)
    arcgis = ArcGISConnector(cache_service)
    
    try:
        service = DataCatalogService(db, socrata, arcgis)
        sources = await service.get_all_sources()
        
        return {
            "count": len(sources),
            "sources": [
                {
                    "name": s.source_name,
                    "type": s.source_type.value,
                    "dataset_id": s.dataset_id,
                    "status": s.status.value,
                    "last_ingest": s.last_successful_ingest_at,
                    "row_count": s.row_count,
                }
                for s in sources
            ],
        }
    finally:
        await socrata.close()
        await arcgis.close()

