"""
Data ingestion jobs for syncing external data sources.
"""
import logging
import hashlib
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.connectors.socrata import SocrataConnector, PROPERTY_INFO_FIELDS
from app.connectors.arcgis import ArcGISConnector, ArcGISService
from app.models.parcels import Parcel, ZoningDistrict
from app.models.sr_311 import ServiceRequest311
from app.services.data_catalog import DataCatalogService

logger = logging.getLogger(__name__)


class DataIngestionJob:
    """
    Job for ingesting data from external sources.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        socrata: SocrataConnector,
        arcgis: ArcGISConnector,
        catalog_service: DataCatalogService,
    ):
        self.db = db
        self.socrata = socrata
        self.arcgis = arcgis
        self.catalog = catalog_service
    
    @staticmethod
    def _compute_parcel_uid(*identifiers) -> str:
        """Compute deterministic parcel_uid from identifiers."""
        combined = "|".join(str(i) for i in identifiers if i)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]
    
    async def ingest_property_info(self):
        """Ingest property information from Socrata."""
        source_name = "ebr_property_info"
        job_id = f"property_info_{datetime.utcnow().isoformat()}"
        
        await self.catalog.record_ingest_start(source_name, job_id)
        
        try:
            # Query all property records
            records = await self.socrata.query_all(
                dataset_id="re5c-hrw9",
                select=PROPERTY_INFO_FIELDS,
            )
            
            logger.info(f"Retrieved {len(records)} property records")
            
            # Upsert parcels
            for record in records:
                parcel_uid = self._compute_parcel_uid(
                    record.get("parcel_id"),
                    record.get("lot_id"),
                    record.get("site_address"),
                )
                
                # Check if exists
                stmt = select(Parcel).where(Parcel.parcel_uid == parcel_uid)
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update
                    for key, value in record.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    existing.source_updated_at = datetime.utcnow()
                else:
                    # Insert
                    parcel = Parcel(
                        parcel_uid=parcel_uid,
                        parcel_id=record.get("parcel_id"),
                        lot_id=record.get("lot_id"),
                        site_address=record.get("site_address"),
                        owner_name=record.get("owner_name"),
                        land_use=record.get("land_use"),
                        municipality=record.get("municipality"),
                        zip_code=record.get("zip"),
                        council_district=record.get("council_district"),
                        latitude=float(record["latitude"]) if record.get("latitude") else None,
                        longitude=float(record["longitude"]) if record.get("longitude") else None,
                        source_system="socrata",
                        raw_data=record,
                    )
                    self.db.add(parcel)
            
            await self.db.commit()
            
            # Compute schema hash
            metadata = await self.socrata.get_metadata("re5c-hrw9")
            schema_hash = self.catalog.compute_schema_hash(
                metadata.get("columns", [])
            )
            
            await self.catalog.record_ingest_success(
                source_name, len(records), schema_hash
            )
            
            logger.info(f"Successfully ingested {len(records)} parcels")
            
        except Exception as e:
            logger.error(f"Property info ingestion failed: {e}")
            await self.catalog.record_ingest_failure(source_name, str(e))
            raise
    
    async def ingest_zoning(self):
        """Ingest zoning districts from ArcGIS."""
        source_name = "ebr_zoning"
        job_id = f"zoning_{datetime.utcnow().isoformat()}"
        
        await self.catalog.record_ingest_start(source_name, job_id)
        
        try:
            features = await self.arcgis.query_all(
                service=ArcGISService.ZONING,
                return_geometry=True,
            )
            
            logger.info(f"Retrieved {len(features)} zoning features")
            
            # Clear existing zoning (full replace strategy)
            from sqlalchemy import delete
            await self.db.execute(delete(ZoningDistrict))
            
            # Insert new zoning
            for feature in features:
                attrs = feature.get("attributes", {})
                # geometry is available but not stored yet; ignore for now
                
                zone = ZoningDistrict(
                    zone_code=attrs.get("ZONE_CODE") or attrs.get("ZONING"),
                    zone_name=attrs.get("ZONE_NAME"),
                    zone_description=attrs.get("DESCRIPTION"),
                    # geometry would be converted from ArcGIS JSON to WKT
                    raw_data=attrs,
                )
                self.db.add(zone)
            
            await self.db.commit()
            
            await self.catalog.record_ingest_success(
                source_name, len(features), "zoning_schema_v1"
            )
            
            logger.info(f"Successfully ingested {len(features)} zoning districts")
            
        except Exception as e:
            logger.error(f"Zoning ingestion failed: {e}")
            await self.catalog.record_ingest_failure(source_name, str(e))
            raise
    
    async def ingest_311_requests(self):
        """Ingest 311 service requests."""
        source_name = "ebr_311"
        job_id = f"sr311_{datetime.utcnow().isoformat()}"
        
        await self.catalog.record_ingest_start(source_name, job_id)
        
        try:
            # Ingest open requests
            open_features = await self.arcgis.query_all(
                service=ArcGISService.SR_311_OPEN,
                return_geometry=True,
            )
            
            # Ingest closed requests (last 90 days only)
            from datetime import timedelta
            ninety_days_ago = datetime.utcnow() - timedelta(days=90)
            closed_features = await self.arcgis.query(
                service=ArcGISService.SR_311_CLOSED,
                where=f"CLOSED_DATE > timestamp '{ninety_days_ago.isoformat()}'",
                return_geometry=True,
            )
            
            all_features = open_features + closed_features.get("features", [])
            
            logger.info(f"Retrieved {len(all_features)} 311 requests")
            
            # Upsert requests
            for feature in all_features:
                attrs = feature.get("attributes", {})
                
                request_id = attrs.get("REQUEST_ID") or attrs.get("OBJECTID")
                if not request_id:
                    continue
                
                stmt = select(ServiceRequest311).where(
                    ServiceRequest311.request_id == str(request_id)
                )
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if not existing:
                    sr = ServiceRequest311(
                        request_id=str(request_id),
                        case_number=attrs.get("CASE_NUMBER"),
                        request_type=attrs.get("REQUEST_TYPE"),
                        description=attrs.get("DESCRIPTION"),
                        status=attrs.get("STATUS"),
                        address=attrs.get("ADDRESS"),
                        # geometry conversion would happen here
                        source_layer="0" if feature in open_features else "1",
                    )
                    self.db.add(sr)
            
            await self.db.commit()
            
            await self.catalog.record_ingest_success(
                source_name, len(all_features), "sr311_schema_v1"
            )
            
            logger.info(f"Successfully ingested {len(all_features)} 311 requests")
            
        except Exception as e:
            logger.error(f"311 ingestion failed: {e}")
            await self.catalog.record_ingest_failure(source_name, str(e))
            raise
    
    async def run_all(self):
        """Run all ingestion jobs."""
        logger.info("Starting data ingestion job suite")
        
        try:
            await self.ingest_property_info()
        except Exception as e:
            logger.error(f"Property info ingestion failed: {e}")
        
        try:
            await self.ingest_zoning()
        except Exception as e:
            logger.error(f"Zoning ingestion failed: {e}")
        
        try:
            await self.ingest_311_requests()
        except Exception as e:
            logger.error(f"311 ingestion failed: {e}")
        
        logger.info("Data ingestion job suite completed")

