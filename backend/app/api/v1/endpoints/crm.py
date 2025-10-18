"""
CRM endpoints for owners, parks, leads, and deals.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, ConfigDict
from datetime import datetime

from app.core.database import get_db
from app.models.crm import Owner, Park, Lead, Deal, PipelineStage, LeadSource

router = APIRouter()


# Pydantic schemas
class OwnerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    mailing_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class OwnerResponse(BaseModel):
    id: UUID
    name: str
    email: Optional[str]
    phone: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParkCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    pad_count: Optional[int] = None
    occupied_pads: Optional[int] = None
    lot_rent: Optional[float] = None
    owner_id: Optional[UUID] = None


class ParkResponse(BaseModel):
    id: UUID
    name: str
    address: Optional[str]
    pad_count: Optional[int]
    occupied_pads: Optional[int]
    lot_rent: Optional[float]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeadCreate(BaseModel):
    park_id: UUID
    owner_id: Optional[UUID] = None
    source: LeadSource
    asking_price: Optional[float] = None
    offer_price: Optional[float] = None


class LeadResponse(BaseModel):
    id: UUID
    park_id: UUID
    source: str
    stage: str
    asking_price: Optional[float]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DealCreate(BaseModel):
    lead_id: UUID
    stage: PipelineStage
    purchase_price: Optional[float] = None
    projected_noi: Optional[float] = None


class DealResponse(BaseModel):
    id: UUID
    lead_id: UUID
    stage: str
    purchase_price: Optional[float]
    projected_noi: Optional[float]
    cap_rate: Optional[float]
    dscr: Optional[float]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Owner endpoints
@router.post("/owners", response_model=OwnerResponse)
async def create_owner(
    owner: OwnerCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new owner."""
    db_owner = Owner(**owner.model_dump())
    db.add(db_owner)
    await db.commit()
    await db.refresh(db_owner)
    return db_owner


@router.get("/owners", response_model=List[OwnerResponse])
async def list_owners(
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List owners with optional search."""
    stmt = select(Owner)
    if search:
        stmt = stmt.where(Owner.name.ilike(f"%{search}%"))
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


# Park endpoints
@router.post("/parks", response_model=ParkResponse)
async def create_park(
    park: ParkCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new park."""
    db_park = Park(**park.model_dump())
    db.add(db_park)
    await db.commit()
    await db.refresh(db_park)
    return db_park


@router.get("/parks", response_model=List[ParkResponse])
async def list_parks(
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List parks with optional search."""
    stmt = select(Park)
    if search:
        stmt = stmt.where(Park.name.ilike(f"%{search}%"))
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/parks/{park_id}", response_model=ParkResponse)
async def get_park(
    park_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get park by ID."""
    stmt = select(Park).where(Park.id == park_id)
    result = await db.execute(stmt)
    park = result.scalar_one_or_none()

    if not park:
        raise HTTPException(status_code=404, detail="Park not found")

    return park


# Lead endpoints
@router.post("/leads", response_model=LeadResponse)
async def create_lead(
    lead: LeadCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new lead."""
    db_lead = Lead(**lead.model_dump())
    db.add(db_lead)
    await db.commit()
    await db.refresh(db_lead)
    return db_lead


@router.get("/leads", response_model=List[LeadResponse])
async def list_leads(
    stage: Optional[PipelineStage] = Query(None),
    source: Optional[LeadSource] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List leads with optional filtering."""
    stmt = select(Lead)
    if stage:
        stmt = stmt.where(Lead.stage == stage)
    if source:
        stmt = stmt.where(Lead.source == source)
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


# Deal endpoints
@router.post("/deals", response_model=DealResponse)
async def create_deal(
    deal: DealCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new deal."""
    db_deal = Deal(**deal.model_dump())
    db.add(db_deal)
    await db.commit()
    await db.refresh(db_deal)
    return db_deal


@router.get("/deals", response_model=List[DealResponse])
async def list_deals(
    stage: Optional[PipelineStage] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List deals with optional stage filtering."""
    stmt = select(Deal)
    if stage:
        stmt = stmt.where(Deal.stage == stage)
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/deals/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get deal by ID."""
    stmt = select(Deal).where(Deal.id == deal_id)
    result = await db.execute(stmt)
    deal = result.scalar_one_or_none()

    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    return deal


@router.get("/pipeline/summary")
async def get_pipeline_summary(
    db: AsyncSession = Depends(get_db),
):
    """Get pipeline summary by stage."""
    from sqlalchemy import func

    stmt = select(
        Deal.stage,
        func.count(Deal.id).label("count"),
        func.sum(Deal.purchase_price).label("total_value"),
    ).group_by(Deal.stage)

    result = await db.execute(stmt)
    rows = result.all()

    return {
        "summary": [
            {
                "stage": row[0].value if row[0] else None,
                "count": row[1],
                "total_value": float(row[2]) if row[2] else 0,
            }
            for row in rows
        ]
    }
