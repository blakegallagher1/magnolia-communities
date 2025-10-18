"""
Data ingestion jobs for syncing external data sources.
"""

import logging
import hashlib
from datetime import datetime
from typing import Any, Iterable, List, Optional, Sequence

from geoalchemy2 import WKTElement
from shapely.geometry import LinearRing, MultiPolygon, Point, Polygon

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

    @staticmethod
    def _clean_ring(ring: Iterable[Sequence[float]]) -> List[tuple[float, float]]:
        """Convert ArcGIS ring coordinate list to cleaned float tuples."""
        cleaned: List[tuple[float, float]] = []
        for point in ring:
            if point is None or len(point) < 2:
                continue
            try:
                cleaned.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                continue
        return cleaned

    @staticmethod
    def _arcgis_polygon_geometry(feature: dict) -> Optional[WKTElement]:
        """Convert ArcGIS polygon feature to WKTElement."""
        geometry = feature.get("geometry") or {}
        rings = geometry.get("rings")
        if not rings:
            return None

        outer_rings: List[List[tuple[float, float]]] = []
        holes: List[List[tuple[float, float]]] = []

        for raw_ring in rings:
            cleaned = DataIngestionJob._clean_ring(raw_ring)
            if len(cleaned) < 3:
                continue
            ring_geom = LinearRing(cleaned)
            # ArcGIS uses clockwise for outer rings, counter-clockwise for holes
            if ring_geom.is_ccw:
                holes.append(cleaned)
            else:
                outer_rings.append(cleaned)

        polygons: List[Polygon] = []
        remaining_holes = holes.copy()

        for outer in outer_rings:
            outer_polygon = Polygon(outer)
            assigned_holes: List[List[tuple[float, float]]] = []

            surviving_holes: List[List[tuple[float, float]]] = []
            for hole in remaining_holes:
                hole_polygon = Polygon(hole)
                if outer_polygon.contains(hole_polygon.representative_point()):
                    assigned_holes.append(hole)
                else:
                    surviving_holes.append(hole)

            remaining_holes = surviving_holes
            polygons.append(Polygon(outer, holes=assigned_holes))

        # Any unassigned holes are actually independent polygons.
        for hole in remaining_holes:
            polygons.append(Polygon(hole))

        if not polygons:
            return None

        if len(polygons) == 1:
            geom = polygons[0]
        else:
            geom = MultiPolygon(polygons)

        if geom.is_empty:
            return None

        return WKTElement(geom.wkt, srid=4326)

    @staticmethod
    def _arcgis_point_geometry(feature: dict) -> tuple[Optional[float], Optional[float], Optional[WKTElement]]:
        """Extract longitude/latitude and WKT point geometry from ArcGIS feature."""
        geometry = feature.get("geometry") or {}
        attrs = feature.get("attributes", {}) or {}

        x = geometry.get("x")
        y = geometry.get("y")

        if x is None:
            x = attrs.get("LONGITUDE") or attrs.get("X")
        if y is None:
            y = attrs.get("LATITUDE") or attrs.get("Y")

        try:
            lon = float(x) if x is not None else None
        except (TypeError, ValueError):
            lon = None

        try:
            lat = float(y) if y is not None else None
        except (TypeError, ValueError):
            lat = None

        if lon is None or lat is None:
            return None, None, None

        wkt = WKTElement(Point(lon, lat).wkt, srid=4326)
        return lon, lat, wkt

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
                        latitude=(
                            float(record["latitude"])
                            if record.get("latitude")
                            else None
                        ),
                        longitude=(
                            float(record["longitude"])
                            if record.get("longitude")
                            else None
                        ),
                        source_system="socrata",
                        raw_data=record,
                    )
                    self.db.add(parcel)

            await self.db.commit()

            # Compute schema hash
            metadata = await self.socrata.get_metadata("re5c-hrw9")
            schema_hash = self.catalog.compute_schema_hash(metadata.get("columns", []))

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
                geom = self._arcgis_polygon_geometry(feature)

                zone = ZoningDistrict(
                    zone_code=attrs.get("ZONE_CODE") or attrs.get("ZONING"),
                    zone_name=attrs.get("ZONE_NAME"),
                    zone_description=attrs.get("DESCRIPTION"),
                    geometry=geom,
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
                attrs = feature.get("attributes", {}) or {}

                request_id = attrs.get("REQUEST_ID") or attrs.get("OBJECTID")
                if not request_id:
                    continue

                stmt = select(ServiceRequest311).where(
                    ServiceRequest311.request_id == str(request_id)
                )
                result = await self.db.execute(stmt)
                existing = result.scalar_one_or_none()

                lon, lat, geom = self._arcgis_point_geometry(feature)
                source_layer = "open" if feature in open_features else "closed"

                payload: dict[str, Any] = {
                    "case_number": attrs.get("CASE_NUMBER"),
                    "request_type": attrs.get("REQUEST_TYPE"),
                    "request_category": attrs.get("REQUEST_CATEGORY"),
                    "description": attrs.get("DESCRIPTION"),
                    "status": attrs.get("STATUS"),
                    "address": attrs.get("ADDRESS"),
                    "parcel_id": attrs.get("PARCEL_ID") or attrs.get("PARCELID"),
                    "source_layer": source_layer,
                }

                if lon is not None:
                    payload["longitude"] = lon
                if lat is not None:
                    payload["latitude"] = lat
                if geom is not None:
                    payload["geometry"] = geom

                if existing:
                    for key, value in payload.items():
                        setattr(existing, key, value)
                else:
                    sr = ServiceRequest311(
                        request_id=str(request_id),
                        **payload,
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
