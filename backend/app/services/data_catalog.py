"""
Data catalog service for tracking data freshness and ingestion.
"""
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_catalog import (
    DataCatalog,
    DataSource,
    DataSourceType,
    DataSourceStatus,
)
from app.connectors.socrata import SocrataConnector
from app.connectors.arcgis import ArcGISConnector

logger = logging.getLogger(__name__)


class DataCatalogService:
    """
    Service for managing data catalog and freshness tracking.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        socrata: SocrataConnector,
        arcgis: ArcGISConnector,
    ):
        self.db = db
        self.socrata = socrata
        self.arcgis = arcgis
    
    async def register_source(
        self,
        source_type: DataSourceType,
        source_name: str,
        dataset_id: str,
        endpoint: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DataCatalog:
        """Register a new data source in the catalog."""
        catalog_entry = DataCatalog(
            source_type=source_type,
            source_name=source_name,
            dataset_id=dataset_id,
            endpoint=endpoint,
            metadata=metadata or {},
        )
        
        self.db.add(catalog_entry)
        await self.db.commit()
        await self.db.refresh(catalog_entry)
        
        logger.info(f"Registered data source: {source_name}")
        return catalog_entry
    
    async def check_freshness(self, source_name: str) -> Dict[str, Any]:
        """
        Check if a data source needs refresh based on remote update time.
        
        Returns:
            Dict with keys: needs_refresh, remote_updated_at, local_updated_at
        """
        # Get catalog entry
        stmt = select(DataCatalog).where(DataCatalog.source_name == source_name)
        result = await self.db.execute(stmt)
        catalog = result.scalar_one_or_none()
        
        if not catalog:
            logger.warning(f"Source not found in catalog: {source_name}")
            return {"needs_refresh": True, "reason": "not_in_catalog"}
        
        # Get remote metadata
        try:
            if catalog.source_type == DataSourceType.SOCRATA:
                remote_meta = await self.socrata.get_metadata(catalog.dataset_id)
                remote_updated_at = remote_meta.get("rowsUpdatedAt")
            elif catalog.source_type == DataSourceType.ARCGIS:
                from app.connectors.arcgis import ArcGISService
                service = ArcGISService(catalog.dataset_id)
                remote_meta = await self.arcgis.get_service_metadata(service)
                # Extract last edit date from ArcGIS metadata
                editing_info = remote_meta.get("editingInfo", {})
                remote_updated_at = editing_info.get("lastEditDate")
            else:
                logger.warning(f"Unknown source type: {catalog.source_type}")
                return {"needs_refresh": False}
            
            # Compare timestamps
            if remote_updated_at:
                remote_dt = datetime.fromisoformat(
                    str(remote_updated_at).replace("Z", "+00:00")
                )
                
                needs_refresh = (
                    not catalog.last_seen_updated_at
                    or remote_dt > catalog.last_seen_updated_at
                )
                
                # Update catalog
                catalog.last_seen_updated_at = remote_dt
                await self.db.commit()
                
                return {
                    "needs_refresh": needs_refresh,
                    "remote_updated_at": remote_dt,
                    "local_updated_at": catalog.last_successful_ingest_at,
                }
            
        except Exception as e:
            logger.error(f"Error checking freshness for {source_name}: {e}")
            catalog.consecutive_failures += 1
            catalog.last_error = str(e)
            
            if catalog.consecutive_failures >= 3:
                catalog.status = DataSourceStatus.DEGRADED
            
            await self.db.commit()
            
            return {"needs_refresh": False, "error": str(e)}
        
        return {"needs_refresh": False}
    
    async def record_ingest_start(
        self, source_name: str, job_id: str
    ) -> None:
        """Record the start of an ingestion job."""
        stmt = select(DataCatalog).where(DataCatalog.source_name == source_name)
        result = await self.db.execute(stmt)
        catalog = result.scalar_one_or_none()
        
        if catalog:
            catalog.last_ingest_at = datetime.utcnow()
            catalog.ingest_job_id = job_id
            await self.db.commit()
    
    async def record_ingest_success(
        self,
        source_name: str,
        row_count: int,
        schema_hash: str,
    ) -> None:
        """Record successful ingestion."""
        stmt = select(DataCatalog).where(DataCatalog.source_name == source_name)
        result = await self.db.execute(stmt)
        catalog = result.scalar_one_or_none()
        
        if catalog:
            catalog.last_successful_ingest_at = datetime.utcnow()
            catalog.row_count = row_count
            catalog.schema_hash = schema_hash
            catalog.status = DataSourceStatus.HEALTHY
            catalog.consecutive_failures = 0
            catalog.last_error = None
            await self.db.commit()
            
            logger.info(
                f"Ingestion success: {source_name} ({row_count} rows)"
            )
    
    async def record_ingest_failure(
        self, source_name: str, error: str
    ) -> None:
        """Record failed ingestion."""
        stmt = select(DataCatalog).where(DataCatalog.source_name == source_name)
        result = await self.db.execute(stmt)
        catalog = result.scalar_one_or_none()
        
        if catalog:
            catalog.consecutive_failures += 1
            catalog.last_error = error
            
            if catalog.consecutive_failures >= 3:
                catalog.status = DataSourceStatus.FAILED
                logger.error(
                    f"Source marked as FAILED: {source_name} "
                    f"(3+ consecutive failures)"
                )
            elif catalog.consecutive_failures >= 1:
                catalog.status = DataSourceStatus.DEGRADED
            
            await self.db.commit()
    
    @staticmethod
    def compute_schema_hash(columns: list) -> str:
        """Compute hash of schema for drift detection."""
        schema_str = ",".join(
            f"{col.get('name')}:{col.get('dataTypeName')}"
            for col in sorted(columns, key=lambda x: x.get("name", ""))
        )
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]
    
    async def get_all_sources(self) -> list[DataCatalog]:
        """Get all registered data sources."""
        stmt = select(DataCatalog)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_health_summary(self) -> Dict[str, Any]:
        """Get overall data health summary."""
        sources = await self.get_all_sources()
        
        return {
            "total_sources": len(sources),
            "healthy": sum(
                1 for s in sources if s.status == DataSourceStatus.HEALTHY
            ),
            "degraded": sum(
                1 for s in sources if s.status == DataSourceStatus.DEGRADED
            ),
            "failed": sum(
                1 for s in sources if s.status == DataSourceStatus.FAILED
            ),
            "sources": [
                {
                    "name": s.source_name,
                    "status": s.status.value,
                    "last_ingest": s.last_successful_ingest_at,
                    "row_count": s.row_count,
                    "consecutive_failures": s.consecutive_failures,
                }
                for s in sources
            ],
        }

