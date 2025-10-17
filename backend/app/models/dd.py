"""
Due Diligence models.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    ForeignKey,
    Integer,
    Enum as SQLEnum,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.core.database import Base


class DDItemStatus(str, enum.Enum):
    """Due diligence item status."""

    PENDING = "pending"
    VERIFIED = "verified"
    ESCROWED = "escrowed"
    DEFERRED = "deferred"


class DDCategory(str, enum.Enum):
    """DD checklist categories."""

    TITLE = "title"
    UTILITIES = "utilities"
    ZONING = "zoning"
    PERMITS = "permits"
    ENVIRONMENTAL = "environmental"
    FLOOD_DRAINAGE = "flood_drainage"
    FINANCIALS = "financials"
    PHYSICAL = "physical"
    LEGAL = "legal"


class RiskLevel(str, enum.Enum):
    """Risk assessment levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DDChecklist(Base):
    """
    Due diligence checklist template.
    """

    __tablename__ = "dd_checklists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Reference
    deal_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Status
    completion_percentage = Column(Integer, default=0)
    risk_score = Column(Integer)  # 0-100
    overall_risk = Column(SQLEnum(RiskLevel))

    # Key findings
    red_flags = Column(JSON)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    items = relationship("DDItem", back_populates="checklist")


class DDItem(Base):
    """
    Individual due diligence checklist items.
    """

    __tablename__ = "dd_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Reference
    checklist_id = Column(
        UUID(as_uuid=True), ForeignKey("dd_checklists.id"), nullable=False
    )
    checklist = relationship("DDChecklist", back_populates="items")

    # Item details
    category = Column(SQLEnum(DDCategory), nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(Text)

    # Status
    status = Column(SQLEnum(DDItemStatus), default=DDItemStatus.PENDING)
    priority = Column(Integer, default=0)

    # Assignment
    assigned_to = Column(String(255))
    due_date = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Risk
    risk_level = Column(SQLEnum(RiskLevel))
    risk_notes = Column(Text)

    # Documents
    document_ids = Column(JSON)  # List of document UUIDs

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Document(Base):
    """
    Document storage metadata (files stored in S3).
    """

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # File details
    filename = Column(String(512), nullable=False)
    file_type = Column(String(100))
    file_size = Column(Integer)  # bytes

    # Storage
    s3_bucket = Column(String(255))
    s3_key = Column(String(1024), nullable=False)

    # Classification
    document_type = Column(String(100))  # loi, psa, rent_roll, insurance, etc.
    tags = Column(JSON)

    # References
    deal_id = Column(UUID(as_uuid=True), index=True)
    park_id = Column(UUID(as_uuid=True), index=True)
    dd_item_id = Column(UUID(as_uuid=True))

    # Access control
    uploaded_by = Column(String(255))
    access_level = Column(
        String(50), default="internal"
    )  # internal, confidential, public

    # Metadata
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
