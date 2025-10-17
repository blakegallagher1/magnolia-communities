"""
Direct mail and campaign management endpoints.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.crm import Campaign

router = APIRouter()


class CampaignCreate(BaseModel):
    name: str
    campaign_type: str  # direct_mail, email, cold_call
    template_id: Optional[str] = None
    merge_fields: Optional[dict] = None
    target_filters: Optional[dict] = None
    touch_count: int = 1
    interval_days: int = 30


class CampaignResponse(BaseModel):
    id: UUID
    name: str
    campaign_type: str
    status: Optional[str]
    sent_count: int
    response_count: int
    launched_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.post("/", response_model=CampaignResponse)
async def create_campaign(
    campaign: CampaignCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new campaign."""
    db_campaign = Campaign(
        **campaign.model_dump(),
        status="draft",
    )
    db.add(db_campaign)
    await db.commit()
    await db.refresh(db_campaign)
    return db_campaign


@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(
    status: Optional[str] = Query(None),
    campaign_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List campaigns with optional filtering."""
    stmt = select(Campaign)
    
    if status:
        stmt = stmt.where(Campaign.status == status)
    if campaign_type:
        stmt = stmt.where(Campaign.campaign_type == campaign_type)
    
    stmt = stmt.limit(limit)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get campaign by ID."""
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign


@router.patch("/{campaign_id}/launch")
async def launch_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Launch a campaign (change status from draft to active)."""
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Campaign must be in draft status to launch"
        )
    
    campaign.status = "active"
    campaign.launched_at = datetime.utcnow()
    await db.commit()
    await db.refresh(campaign)
    
    return {"status": "success", "campaign": campaign}


@router.get("/{campaign_id}/performance")
async def get_campaign_performance(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get campaign performance metrics.
    
    Returns:
    - sent_count
    - response_count
    - response_rate
    - leads_generated
    - cost_per_lead (if cost data available)
    """
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    response_rate = (
        (campaign.response_count / campaign.sent_count)
        if campaign.sent_count > 0
        else 0
    )
    
    # TODO: Query leads generated from this campaign
    # For now, return placeholder
    leads_generated = 0
    
    return {
        "campaign_id": campaign_id,
        "name": campaign.name,
        "sent_count": campaign.sent_count,
        "response_count": campaign.response_count,
        "response_rate": response_rate,
        "leads_generated": leads_generated,
        "status": campaign.status,
    }

