"""
Parcel overlay service for spatial joins and enrichment.
Combines parcel data with zoning, city limits, 311, and adjudication.
"""
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_Intersects, ST_Within, ST_DWithin, ST_Distance

from app.models.parcels import Parcel, ZoningDistrict, CityLimit, AdjudicatedParcel
from app.models.sr_311 import ServiceRequest311

logger = logging.getLogger(__name__)


class ParcelOverlayService:
    """
    Service for spatial overlays and parcel enrichment.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_parcel_overlay(
        self, parcel_uid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive overlay for a parcel including:
        - Zoning district
        - City limits
        - Adjudication status
        - 311 request density
        """
        # Get parcel
        stmt = select(Parcel).where(Parcel.parcel_uid == parcel_uid)
        result = await self.db.execute(stmt)
        parcel = result.scalar_one_or_none()
        
        if not parcel or not parcel.geometry:
            return None
        
        # Get zoning
        zoning = await self._get_zoning(parcel)
        
        # Get city limits
        city = await self._get_city(parcel)
        
        # Check adjudication
        is_adjudicated = await self._check_adjudication(parcel_uid)
        
        # Get 311 density
        sr_311_stats = await self._get_311_stats(parcel)
        
        return {
            "parcel_uid": parcel_uid,
            "parcel_id": parcel.parcel_id,
            "site_address": parcel.site_address,
            "owner_name": parcel.owner_name,
            "zoning": zoning,
            "city": city,
            "adjudicated": is_adjudicated,
            "sr_311_stats": sr_311_stats,
            "latitude": parcel.latitude,
            "longitude": parcel.longitude,
        }
    
    async def _get_zoning(self, parcel: Parcel) -> Optional[Dict[str, Any]]:
        """Get zoning district for parcel."""
        stmt = select(ZoningDistrict).where(
            ST_Intersects(ZoningDistrict.geometry, parcel.geometry)
        )
        result = await self.db.execute(stmt)
        zoning = result.scalar_one_or_none()
        
        if zoning:
            return {
                "zone_code": zoning.zone_code,
                "zone_name": zoning.zone_name,
                "zone_description": zoning.zone_description,
            }
        return None
    
    async def _get_city(self, parcel: Parcel) -> Optional[Dict[str, Any]]:
        """Get city limits for parcel."""
        stmt = select(CityLimit).where(
            ST_Within(parcel.geometry, CityLimit.geometry)
        )
        result = await self.db.execute(stmt)
        city = result.scalar_one_or_none()
        
        if city:
            return {
                "city_name": city.city_name,
                "city_code": city.city_code,
            }
        return None
    
    async def _check_adjudication(self, parcel_uid: str) -> bool:
        """Check if parcel is adjudicated."""
        stmt = select(func.count()).select_from(AdjudicatedParcel).where(
            AdjudicatedParcel.parcel_uid == parcel_uid
        )
        result = await self.db.execute(stmt)
        count = result.scalar()
        return count > 0
    
    async def _get_311_stats(
        self, parcel: Parcel, radius_meters: float = 500
    ) -> Dict[str, Any]:
        """
        Get 311 service request statistics within radius of parcel.
        """
        if not parcel.geometry:
            return {"total": 0, "open": 0, "by_type": {}}
        
        # Count total within radius
        total_stmt = (
            select(func.count())
            .select_from(ServiceRequest311)
            .where(
                ST_DWithin(
                    ServiceRequest311.geometry,
                    parcel.geometry,
                    radius_meters
                )
            )
        )
        total_result = await self.db.execute(total_stmt)
        total = total_result.scalar() or 0
        
        # Count open
        open_stmt = (
            select(func.count())
            .select_from(ServiceRequest311)
            .where(
                and_(
                    ST_DWithin(
                        ServiceRequest311.geometry,
                        parcel.geometry,
                        radius_meters
                    ),
                    ServiceRequest311.status.in_(["Open", "In Progress"])
                )
            )
        )
        open_result = await self.db.execute(open_stmt)
        open_count = open_result.scalar() or 0
        
        # Count by type
        type_stmt = (
            select(
                ServiceRequest311.request_type,
                func.count(ServiceRequest311.id).label("count")
            )
            .where(
                ST_DWithin(
                    ServiceRequest311.geometry,
                    parcel.geometry,
                    radius_meters
                )
            )
            .group_by(ServiceRequest311.request_type)
        )
        type_result = await self.db.execute(type_stmt)
        by_type = {row[0]: row[1] for row in type_result}
        
        return {
            "total": total,
            "open": open_count,
            "by_type": by_type,
            "radius_meters": radius_meters,
        }
    
    async def find_parcels_in_zone(
        self, zone_code: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Find all parcels in a zoning district."""
        stmt = (
            select(Parcel)
            .join(
                ZoningDistrict,
                ST_Intersects(Parcel.geometry, ZoningDistrict.geometry)
            )
            .where(ZoningDistrict.zone_code == zone_code)
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        parcels = result.scalars().all()
        
        return [
            {
                "parcel_uid": p.parcel_uid,
                "parcel_id": p.parcel_id,
                "site_address": p.site_address,
                "owner_name": p.owner_name,
            }
            for p in parcels
        ]
    
    async def find_adjudicated_parcels(
        self, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Find all adjudicated parcels."""
        stmt = select(AdjudicatedParcel).limit(limit)
        result = await self.db.execute(stmt)
        parcels = result.scalars().all()
        
        return [
            {
                "parcel_uid": p.parcel_uid,
                "parcel_id": p.parcel_id,
                "site_address": p.site_address,
                "owner_name": p.owner_name,
                "adjudication_date": p.adjudication_date,
                "status": p.status,
            }
            for p in parcels
        ]
    
    async def find_high_311_parcels(
        self, threshold: int = 5, radius_meters: float = 500, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Find parcels with high 311 request density (blight indicator).
        """
        # This is a complex spatial query - use raw SQL for efficiency
        query = text("""
            SELECT 
                p.parcel_uid,
                p.parcel_id,
                p.site_address,
                p.owner_name,
                COUNT(sr.id) as sr_count
            FROM parcels p
            LEFT JOIN service_requests_311 sr 
                ON ST_DWithin(sr.geometry, p.geometry, :radius)
            WHERE p.geometry IS NOT NULL
            GROUP BY p.parcel_uid, p.parcel_id, p.site_address, p.owner_name
            HAVING COUNT(sr.id) >= :threshold
            ORDER BY sr_count DESC
            LIMIT :limit
        """)
        
        result = await self.db.execute(
            query,
            {"radius": radius_meters, "threshold": threshold, "limit": limit}
        )
        
        return [
            {
                "parcel_uid": row[0],
                "parcel_id": row[1],
                "site_address": row[2],
                "owner_name": row[3],
                "sr_311_count": row[4],
            }
            for row in result
        ]

