"""
Due diligence checklist and document management endpoints.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.dd import (
    DDChecklist, DDItem,
    DDItemStatus, DDCategory, RiskLevel
)

router = APIRouter()


# Pydantic schemas
class DDChecklistCreate(BaseModel):
    deal_id: UUID


class DDChecklistResponse(BaseModel):
    id: UUID
    deal_id: UUID
    completion_percentage: int
    risk_score: Optional[int]
    overall_risk: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class DDItemCreate(BaseModel):
    checklist_id: UUID
    category: DDCategory
    title: str
    description: Optional[str] = None
    priority: int = 0
    risk_level: Optional[RiskLevel] = None


class DDItemUpdate(BaseModel):
    status: Optional[DDItemStatus] = None
    assigned_to: Optional[str] = None
    risk_notes: Optional[str] = None
    completed_at: Optional[datetime] = None


class DDItemResponse(BaseModel):
    id: UUID
    checklist_id: UUID
    category: str
    title: str
    status: str
    priority: int
    risk_level: Optional[str]
    assigned_to: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# Checklist endpoints
@router.post("/checklists", response_model=DDChecklistResponse)
async def create_checklist(
    checklist: DDChecklistCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new DD checklist for a deal."""
    db_checklist = DDChecklist(**checklist.model_dump())
    db.add(db_checklist)
    await db.commit()
    await db.refresh(db_checklist)
    
    # Create default checklist items
    default_items = _get_default_checklist_items(db_checklist.id)
    for item in default_items:
        db.add(item)
    await db.commit()
    
    return db_checklist


@router.get("/checklists/{checklist_id}", response_model=DDChecklistResponse)
async def get_checklist(
    checklist_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get DD checklist by ID."""
    stmt = select(DDChecklist).where(DDChecklist.id == checklist_id)
    result = await db.execute(stmt)
    checklist = result.scalar_one_or_none()
    
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    
    return checklist


@router.get("/checklists/{checklist_id}/items", response_model=List[DDItemResponse])
async def get_checklist_items(
    checklist_id: UUID,
    category: Optional[DDCategory] = None,
    status: Optional[DDItemStatus] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get all items for a checklist."""
    stmt = select(DDItem).where(DDItem.checklist_id == checklist_id)
    
    if category:
        stmt = stmt.where(DDItem.category == category)
    if status:
        stmt = stmt.where(DDItem.status == status)
    
    result = await db.execute(stmt)
    return list(result.scalars().all())


# Item endpoints
@router.post("/items", response_model=DDItemResponse)
async def create_item(
    item: DDItemCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new DD checklist item."""
    db_item = DDItem(**item.model_dump())
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    
    # Update checklist completion percentage
    await _update_checklist_completion(db, item.checklist_id)
    
    return db_item


@router.patch("/items/{item_id}", response_model=DDItemResponse)
async def update_item(
    item_id: UUID,
    update: DDItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update DD checklist item."""
    stmt = select(DDItem).where(DDItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Update fields
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    
    await db.commit()
    await db.refresh(item)
    
    # Update checklist completion
    await _update_checklist_completion(db, item.checklist_id)
    
    return item


# Helper functions
def _get_default_checklist_items(checklist_id: UUID) -> List[DDItem]:
    """
    Generate default Louisiana/EBR DD checklist items.
    """
    items = [
        # Title
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.TITLE,
            title="Title Report & Survey",
            description="Obtain title report and current survey",
            priority=1,
            risk_level=RiskLevel.HIGH,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.TITLE,
            title="Lien Search",
            description="Search for liens, judgments, tax obligations",
            priority=1,
            risk_level=RiskLevel.HIGH,
        ),
        # Utilities
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.UTILITIES,
            title="Water Service Verification",
            description="Verify water service provider and capacity",
            priority=2,
            risk_level=RiskLevel.MEDIUM,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.UTILITIES,
            title="Sewer/Septic Assessment",
            description="Assess sewer connection or septic system condition",
            priority=2,
            risk_level=RiskLevel.MEDIUM,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.UTILITIES,
            title="Electric Service",
            description="Verify electric service and capacity",
            priority=2,
            risk_level=RiskLevel.LOW,
        ),
        # Zoning
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.ZONING,
            title="Zoning Verification (EBRGIS)",
            description="Verify current zoning allows MHP use",
            priority=1,
            risk_level=RiskLevel.HIGH,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.ZONING,
            title="Comprehensive Zoning Ordinance Compliance",
            description="Review EBR comprehensive zoning ordinance compliance",
            priority=2,
            risk_level=RiskLevel.MEDIUM,
        ),
        # Permits
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.PERMITS,
            title="MHP License",
            description="Verify current mobile home park license",
            priority=1,
            risk_level=RiskLevel.HIGH,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.PERMITS,
            title="Certificate of Occupancy",
            description="Obtain all certificates of occupancy",
            priority=2,
            risk_level=RiskLevel.MEDIUM,
        ),
        # Environmental
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.ENVIRONMENTAL,
            title="Phase I Environmental",
            description="Conduct Phase I Environmental Site Assessment",
            priority=1,
            risk_level=RiskLevel.HIGH,
        ),
        # Flood/Drainage
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.FLOOD_DRAINAGE,
            title="Flood Zone Determination",
            description="Determine FEMA flood zone and insurance requirements",
            priority=1,
            risk_level=RiskLevel.HIGH,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.FLOOD_DRAINAGE,
            title="Drainage Assessment",
            description="Assess site drainage and proximity to 311 drainage complaints",
            priority=2,
            risk_level=RiskLevel.MEDIUM,
        ),
        # Financials
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.FINANCIALS,
            title="Rent Roll Verification",
            description="Verify current rent roll with 100% verification",
            priority=1,
            risk_level=RiskLevel.HIGH,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.FINANCIALS,
            title="Operating Expense Review",
            description="Review trailing 24 months operating expenses",
            priority=1,
            risk_level=RiskLevel.HIGH,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.FINANCIALS,
            title="Property Tax Review",
            description="Verify current property tax assessment",
            priority=2,
            risk_level=RiskLevel.MEDIUM,
        ),
        # Physical
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.PHYSICAL,
            title="Property Inspection",
            description="Conduct comprehensive property inspection",
            priority=1,
            risk_level=RiskLevel.HIGH,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.PHYSICAL,
            title="CapEx Reserve Study",
            description="Develop capital expenditure reserve forecast",
            priority=2,
            risk_level=RiskLevel.MEDIUM,
        ),
        # Legal
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.LEGAL,
            title="Review Tenant Leases",
            description="Review sample tenant lease agreements",
            priority=2,
            risk_level=RiskLevel.MEDIUM,
        ),
        DDItem(
            checklist_id=checklist_id,
            category=DDCategory.LEGAL,
            title="HOA/Covenant Review",
            description="Review any HOA documents or deed restrictions",
            priority=2,
            risk_level=RiskLevel.LOW,
        ),
    ]
    
    return items


async def _update_checklist_completion(
    db: AsyncSession, checklist_id: UUID
):
    """Update checklist completion percentage and risk score."""
    # Get all items
    stmt = select(DDItem).where(DDItem.checklist_id == checklist_id)
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    
    if not items:
        return
    
    # Calculate completion
    completed = sum(
        1 for item in items
        if item.status in [DDItemStatus.VERIFIED, DDItemStatus.ESCROWED]
    )
    completion_pct = int((completed / len(items)) * 100)
    
    # Calculate risk score (weighted by item risk level)
    risk_weights = {
        RiskLevel.LOW: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3,
        RiskLevel.CRITICAL: 4,
    }
    
    total_risk = 0
    max_risk = 0
    
    for item in items:
        weight = risk_weights.get(item.risk_level, 2)
        max_risk += weight * 4  # Max score per item
        
        if item.status == DDItemStatus.PENDING:
            total_risk += weight * 4
        elif item.status == DDItemStatus.DEFERRED:
            total_risk += weight * 2
        # Verified and Escrowed add no risk
    
    risk_score = int((total_risk / max_risk) * 100) if max_risk > 0 else 0
    
    # Determine overall risk
    if risk_score >= 75:
        overall_risk = RiskLevel.CRITICAL
    elif risk_score >= 50:
        overall_risk = RiskLevel.HIGH
    elif risk_score >= 25:
        overall_risk = RiskLevel.MEDIUM
    else:
        overall_risk = RiskLevel.LOW
    
    # Update checklist
    stmt = select(DDChecklist).where(DDChecklist.id == checklist_id)
    result = await db.execute(stmt)
    checklist = result.scalar_one_or_none()
    
    if checklist:
        checklist.completion_percentage = completion_pct
        checklist.risk_score = risk_score
        checklist.overall_risk = overall_risk
        await db.commit()

