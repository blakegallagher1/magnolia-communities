"""
Parcel and overlay endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.parcels import Parcel
from app.services.parcel_overlay import ParcelOverlayService

router = APIRouter()


class ParcelResponse(BaseModel):
    """Parcel response schema."""

    parcel_uid: str
    parcel_id: Optional[str]
    site_address: Optional[str]
    owner_name: Optional[str]
    land_use: Optional[str]
    municipality: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]

    class Config:
        from_attributes = True


class ParcelOverlayResponse(BaseModel):
    """Parcel overlay response schema."""

    parcel_uid: str
    parcel_id: Optional[str]
    site_address: Optional[str]
    owner_name: Optional[str]
    zoning: Optional[dict]
    city: Optional[dict]
    adjudicated: bool
    sr_311_stats: dict
    latitude: Optional[float]
    longitude: Optional[float]


@router.get("/search", response_model=List[ParcelResponse])
async def search_parcels(
    address: Optional[str] = Query(None, description="Search by address"),
    owner: Optional[str] = Query(None, description="Search by owner name"),
    parcel_id: Optional[str] = Query(None, description="Search by parcel ID"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Search parcels by address, owner, or parcel ID."""
    stmt = select(Parcel)

    if address:
        stmt = stmt.where(Parcel.site_address.ilike(f"%{address}%"))
    if owner:
        stmt = stmt.where(Parcel.owner_name.ilike(f"%{owner}%"))
    if parcel_id:
        stmt = stmt.where(Parcel.parcel_id == parcel_id)

    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    parcels = result.scalars().all()

    return parcels


@router.get("/{parcel_uid}", response_model=ParcelResponse)
async def get_parcel(
    parcel_uid: str,
    db: AsyncSession = Depends(get_db),
):
    """Get parcel by UID."""
    stmt = select(Parcel).where(Parcel.parcel_uid == parcel_uid)
    result = await db.execute(stmt)
    parcel = result.scalar_one_or_none()

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    return parcel


@router.get("/{parcel_uid}/overlay", response_model=ParcelOverlayResponse)
async def get_parcel_overlay(
    parcel_uid: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get comprehensive parcel overlay including:
    - Zoning district
    - City limits
    - Adjudication status
    - 311 request density
    """
    service = ParcelOverlayService(db)
    overlay = await service.get_parcel_overlay(parcel_uid)

    if not overlay:
        raise HTTPException(status_code=404, detail="Parcel not found")

    return overlay


@router.get("/adjudicated/list")
async def list_adjudicated_parcels(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List all adjudicated (tax-foreclosed) parcels."""
    service = ParcelOverlayService(db)
    parcels = await service.find_adjudicated_parcels(limit=limit)
    return {"count": len(parcels), "parcels": parcels}


@router.get("/high-311/list")
async def list_high_311_parcels(
    threshold: int = Query(5, ge=1, description="Min 311 requests"),
    radius_meters: float = Query(500, ge=100, le=2000),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Find parcels with high 311 request density (blight indicator)."""
    service = ParcelOverlayService(db)
    parcels = await service.find_high_311_parcels(
        threshold=threshold,
        radius_meters=radius_meters,
        limit=limit,
    )
    return {"count": len(parcels), "parcels": parcels}
