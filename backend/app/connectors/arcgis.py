"""
ArcGIS REST API connector for EBRGIS map services.
Supports query operations, spatial queries, and pagination.
"""

import logging
from typing import List, Dict, Any, Optional
from enum import Enum
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.config import settings
from app.core.redis import CacheService

logger = logging.getLogger(__name__)


class ArcGISService(str, Enum):
    """EBR ArcGIS map service endpoints."""

    # Cadastral services
    TAX_PARCEL = "Cadastral/Tax_Parcel/MapServer/0"
    ADJUDICATED_PARCEL = "Cadastral/Adjudicated_Parcel/MapServer/0"
    LOT_LOOKUP = "Cadastral/Lot_Lookup/MapServer/0"
    ZONING = "Cadastral/Zoning/MapServer/0"
    SUBJECT_PROPERTY = "Cadastral/Subject_Property/MapServer/1"

    # Governmental services
    CITY_LIMIT = "Governmental_Units/City_Limit/MapServer/0"

    # 311 Services (different base URL)
    SR_311_OPEN = "311_Citizen_Request_for_Service___All_Requests/FeatureServer/0"
    SR_311_CLOSED = "311_Citizen_Request_for_Service___All_Requests/FeatureServer/1"


class SpatialRelationship(str, Enum):
    """Spatial relationship types for queries."""

    INTERSECTS = "esriSpatialRelIntersects"
    CONTAINS = "esriSpatialRelContains"
    WITHIN = "esriSpatialRelWithin"
    TOUCHES = "esriSpatialRelTouches"


class ArcGISConnector:
    """
    Connector for ArcGIS REST API with query building and caching.

    Example usage:
        connector = ArcGISConnector(cache_service)
        parcels = await connector.query(
            service=ArcGISService.TAX_PARCEL,
            where="parcel_id='123456789'",
            out_fields=["parcel_id", "owner_name", "site_address"]
        )
    """

    def __init__(self, cache_service: CacheService):
        self.base_url = settings.ARCGIS_BASE_URL
        self.sr_311_base_url = settings.ARCGIS_311_BASE_URL
        self.max_record_count = settings.ARCGIS_MAX_RECORD_COUNT
        self.cache = cache_service
        self.client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    def _get_service_url(self, service: ArcGISService) -> str:
        """Get full URL for a service."""
        if service in [ArcGISService.SR_311_OPEN, ArcGISService.SR_311_CLOSED]:
            return f"{self.sr_311_base_url}/{service.value}"
        return f"{self.base_url}/{service.value}"

    def _build_cache_key(
        self,
        service: ArcGISService,
        where: Optional[str] = None,
        out_fields: Optional[List[str]] = None,
        geometry: Optional[str] = None,
    ) -> str:
        """Generate cache key from query parameters."""
        parts = [
            f"arcgis:{service.value}",
            f"where:{where or '1=1'}",
            f"fields:{','.join(out_fields) if out_fields else '*'}",
            f"geom:{geometry or 'none'}",
        ]
        return ":".join(parts)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def query(
        self,
        service: ArcGISService,
        where: str = "1=1",
        out_fields: Optional[List[str]] = None,
        return_geometry: bool = True,
        geometry: Optional[str] = None,
        geometry_type: Optional[str] = None,
        spatial_rel: SpatialRelationship = SpatialRelationship.INTERSECTS,
        result_offset: int = 0,
        result_record_count: Optional[int] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Query an ArcGIS feature service.

        Args:
            service: ArcGIS service enum
            where: SQL WHERE clause
            out_fields: List of fields to return (default: all)
            return_geometry: Include geometry in results
            geometry: Geometry for spatial query (JSON string)
            geometry_type: Type of geometry (esriGeometryPoint, esriGeometryPolygon, etc.)
            spatial_rel: Spatial relationship for query
            result_offset: Offset for pagination
            result_record_count: Max records to return
            use_cache: Whether to use Redis cache

        Returns:
            Response dictionary with 'features' array
        """
        # Check cache first
        cache_key = self._build_cache_key(service, where, out_fields, geometry)

        if use_cache and result_offset == 0:
            cached = await self.cache.get(cache_key)
            if cached:
                logger.info(f"Cache hit for {service.value}")
                return cached

        # Build query parameters
        params = {
            "where": where,
            "outFields": ",".join(out_fields) if out_fields else "*",
            "returnGeometry": "true" if return_geometry else "false",
            "f": "json",
        }

        if geometry:
            params["geometry"] = geometry
            params["geometryType"] = geometry_type or "esriGeometryPolygon"
            params["spatialRel"] = spatial_rel.value

        if result_offset:
            params["resultOffset"] = result_offset

        if result_record_count:
            params["resultRecordCount"] = min(
                result_record_count, self.max_record_count
            )
        else:
            params["resultRecordCount"] = self.max_record_count

        # Make request
        url = f"{self._get_service_url(service)}/query"
        logger.info(f"Querying ArcGIS: {url}")

        response = await self.client.get(url, params=params)
        response.raise_for_status()

        result = response.json()

        # Check for errors in response
        if "error" in result:
            raise Exception(f"ArcGIS API error: {result['error']}")

        # Cache results
        if use_cache and result_offset == 0:
            await self.cache.set(cache_key, result)

        feature_count = len(result.get("features", []))
        logger.info(f"Retrieved {feature_count} features from {service.value}")

        return result

    async def query_all(
        self,
        service: ArcGISService,
        where: str = "1=1",
        out_fields: Optional[List[str]] = None,
        return_geometry: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Query all features by paginating through service.

        Returns:
            List of all feature dictionaries
        """
        all_features = []
        offset = 0

        while True:
            result = await self.query(
                service=service,
                where=where,
                out_fields=out_fields,
                return_geometry=return_geometry,
                result_offset=offset,
                use_cache=False,
            )

            features = result.get("features", [])
            if not features:
                break

            all_features.extend(features)
            offset += len(features)

            logger.info(
                f"Retrieved {len(all_features)} total features from {service.value}"
            )

            # Stop if we got fewer records than max
            if len(features) < self.max_record_count:
                break

        return all_features

    async def get_service_metadata(self, service: ArcGISService) -> Dict[str, Any]:
        """
        Get metadata for a service including fields and update info.

        Returns metadata with:
            - name: service name
            - type: service type
            - fields: field definitions
            - geometryType: geometry type
            - extent: spatial extent
            - editingInfo: last edit date
        """
        # Remove /query suffix for metadata endpoint
        url = self._get_service_url(service)

        response = await self.client.get(url, params={"f": "json"})
        response.raise_for_status()

        return response.json()

    async def spatial_query(
        self,
        service: ArcGISService,
        geometry: Dict[str, Any],
        geometry_type: str = "esriGeometryPoint",
        spatial_rel: SpatialRelationship = SpatialRelationship.INTERSECTS,
        out_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform spatial query (e.g., find features intersecting a point/polygon).

        Args:
            service: Target service
            geometry: Geometry dict (e.g., {"x": -91.187, "y": 30.458})
            geometry_type: Type of geometry
            spatial_rel: Spatial relationship
            out_fields: Fields to return

        Returns:
            List of matching features
        """
        import json

        result = await self.query(
            service=service,
            geometry=json.dumps(geometry),
            geometry_type=geometry_type,
            spatial_rel=spatial_rel,
            out_fields=out_fields,
            return_geometry=True,
        )

        return result.get("features", [])
