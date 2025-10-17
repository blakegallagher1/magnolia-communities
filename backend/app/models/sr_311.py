"""
311 Service Request models.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
import uuid

from app.core.database import Base


class ServiceRequest311(Base):
    """
    311 citizen service requests (blight, code violations, drainage, etc.).
    """
    __tablename__ = "service_requests_311"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Request identifiers
    request_id = Column(String(100), unique=True, nullable=False, index=True)
    case_number = Column(String(100), index=True)
    
    # Request details
    request_type = Column(String(255), index=True)
    request_category = Column(String(255))
    description = Column(Text)
    status = Column(String(100), index=True)
    
    # Location
    address = Column(String(512))
    latitude = Column(Float)
    longitude = Column(Float)
    geometry = Column(Geometry('POINT', srid=4326))
    
    # Parcel reference
    parcel_id = Column(String(100), index=True)
    
    # Dates
    opened_at = Column(DateTime(timezone=True), index=True)
    closed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    
    # Source metadata
    source_layer = Column(String(50))  # 0=open/in-progress, 1=closed
    ingested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_sr311_geom', 'geometry', postgresql_using='gist'),
        Index('idx_sr311_dates', 'opened_at', 'closed_at'),
    )

