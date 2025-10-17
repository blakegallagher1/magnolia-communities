"""
CRM models for owners, parks, leads, deals, and campaigns.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, Boolean,
    ForeignKey, Enum as SQLEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import enum

from app.core.database import Base


class PipelineStage(str, enum.Enum):
    """Deal pipeline stages."""
    SOURCED = "sourced"
    CONTACTED = "contacted"
    LOI = "loi"
    DD = "dd"
    CLOSING = "closing"
    STABILIZATION = "stabilization"
    EXIT = "exit"


class LeadSource(str, enum.Enum):
    """Lead source types."""
    DIRECT_MAIL = "direct_mail"
    BROKER = "broker"
    ONLINE = "online"
    REFERRAL = "referral"
    COLD_CALL = "cold_call"
    HEIR_SOURCING = "heir_sourcing"
    OTHER = "other"


class Owner(Base):
    """
    Property owners (current or prospective).
    """
    __tablename__ = "owners"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identity
    name = Column(String(512), nullable=False, index=True)
    email = Column(String(255), index=True)
    phone = Column(String(50))
    
    # Address
    mailing_address = Column(Text)
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    
    # Classification
    owner_type = Column(String(50))  # individual, LLC, trust, estate, etc.
    tags = Column(JSON)
    
    # Consent flags
    marketing_consent = Column(Boolean, default=False)
    contact_consent = Column(Boolean, default=True)
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    parks = relationship("Park", back_populates="owner")
    leads = relationship("Lead", back_populates="owner")


class Park(Base):
    """
    Mobile home parks (properties we're tracking or operating).
    """
    __tablename__ = "parks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identity
    name = Column(String(255), nullable=False, index=True)
    
    # Location
    address = Column(String(512))
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Parcel reference
    parcel_uid = Column(String(64), index=True)
    
    # Characteristics
    pad_count = Column(Integer)
    occupied_pads = Column(Integer)
    lot_rent = Column(Float)
    
    # Classification
    parish = Column(String(100))
    zoning = Column(String(50))
    council_district = Column(String(10))
    flood_zone = Column(String(50))
    
    # Flags
    adjudicated_flag = Column(Boolean, default=False)
    blight_index = Column(Float)
    
    # Owner
    owner_id = Column(UUID(as_uuid=True), ForeignKey("owners.id"))
    owner = relationship("Owner", back_populates="parks")
    
    # Tags
    tags = Column(JSON)
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    leads = relationship("Lead", back_populates="park")


class Lead(Base):
    """
    Acquisition leads.
    """
    __tablename__ = "leads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # References
    park_id = Column(UUID(as_uuid=True), ForeignKey("parks.id"), nullable=False)
    park = relationship("Park", back_populates="leads")
    
    owner_id = Column(UUID(as_uuid=True), ForeignKey("owners.id"))
    owner = relationship("Owner", back_populates="leads")
    
    # Source
    source = Column(SQLEnum(LeadSource), nullable=False)
    source_campaign_id = Column(UUID(as_uuid=True))
    
    # Status
    stage = Column(SQLEnum(PipelineStage), default=PipelineStage.SOURCED)
    
    # Financials
    asking_price = Column(Float)
    offer_price = Column(Float)
    
    # Metadata
    notes = Column(Text)
    tags = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    deals = relationship("Deal", back_populates="lead")
    touchpoints = relationship("Touchpoint", back_populates="lead")


class Deal(Base):
    """
    Active deals in the pipeline.
    """
    __tablename__ = "deals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    lead = relationship("Lead", back_populates="deals")
    
    # Status
    stage = Column(SQLEnum(PipelineStage), nullable=False)
    stage_entered_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Financials
    purchase_price = Column(Float)
    estimated_capex = Column(Float)
    projected_noi = Column(Float)
    cap_rate = Column(Float)
    dscr = Column(Float)
    
    # Key dates
    loi_date = Column(DateTime(timezone=True))
    psa_date = Column(DateTime(timezone=True))
    dd_start_date = Column(DateTime(timezone=True))
    dd_end_date = Column(DateTime(timezone=True))
    closing_date = Column(DateTime(timezone=True))
    
    # Decision log (immutable)
    decision_log = Column(JSON)
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Touchpoint(Base):
    """
    Contact touchpoints with leads/owners.
    """
    __tablename__ = "touchpoints"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # References
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    lead = relationship("Lead", back_populates="touchpoints")
    
    # Touchpoint details
    touchpoint_type = Column(String(50))  # email, call, letter, meeting
    subject = Column(String(512))
    notes = Column(Text)
    
    # Attribution
    campaign_id = Column(UUID(as_uuid=True))
    
    # Metadata
    occurred_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(String(255))


class Campaign(Base):
    """
    Direct mail and marketing campaigns.
    """
    __tablename__ = "campaigns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Identity
    name = Column(String(255), nullable=False)
    campaign_type = Column(String(50))  # direct_mail, email, cold_call
    
    # Configuration
    template_id = Column(String(255))
    merge_fields = Column(JSON)  # [Owner_Name], [Parcel_ID], etc.
    
    # Targeting
    target_filters = Column(JSON)
    
    # Sequence
    touch_count = Column(Integer, default=1)
    interval_days = Column(Integer, default=30)
    
    # Status
    status = Column(String(50))  # draft, active, paused, completed
    
    # Stats
    sent_count = Column(Integer, default=0)
    response_count = Column(Integer, default=0)
    
    # Dates
    launched_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

