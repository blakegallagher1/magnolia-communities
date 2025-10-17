"""
Parcel and property-related models.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry
import uuid

from app.core.database import Base


class Parcel(Base):
    """
    Tax parcels from EBRGIS with normalized parcel_uid.
    """
    __tablename__ = "parcels"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Normalized parcel identifier (deterministic hash)
    parcel_uid = Column(String(64), unique=True, nullable=False, index=True)
    
    # Source identifiers
    parcel_id = Column(String(100), index=True)
    assessment_num = Column(String(100), index=True)
    lot_id = Column(String(100), index=True)
    
    # Address
    site_address = Column(String(512), index=True)
    street_num = Column(String(50))
    street_name = Column(String(255))
    city = Column(String(100))
    zip_code = Column(String(10))
    
    # Owner information
    owner_name = Column(String(512), index=True)
    owner_address = Column(Text)
    
    # Property characteristics
    land_use = Column(String(255))
    naics = Column(String(20))
    subdivision = Column(String(255))
    municipality = Column(String(100))
    council_district = Column(String(10))
    
    # Location
    latitude = Column(Float)
    longitude = Column(Float)
    geometry = Column(Geometry('POLYGON', srid=4326))
    
    # Source metadata
    source_system = Column(String(50))
    source_url = Column(Text)
    source_updated_at = Column(DateTime(timezone=True))
    
    # Ingestion metadata
    ingested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    raw_data = Column(JSON)
    
    __table_args__ = (
        Index('idx_parcels_geom', 'geometry', postgresql_using='gist'),
        Index('idx_parcels_location', 'latitude', 'longitude'),
    )


class Lot(Base):
    """
    Recorded lot boundaries from Lot_Lookup service.
    """
    __tablename__ = "lots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    lot_id = Column(String(100), unique=True, nullable=False, index=True)
    lot_number = Column(String(50))
    square = Column(String(50))
    subdivision = Column(String(255))
    
    # Geometry
    geometry = Column(Geometry('POLYGON', srid=4326))
    
    # Source metadata
    source_updated_at = Column(DateTime(timezone=True))
    ingested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    raw_data = Column(JSON)
    
    __table_args__ = (
        Index('idx_lots_geom', 'geometry', postgresql_using='gist'),
    )


class ZoningDistrict(Base):
    """
    Zoning districts from EBRGIS.
    """
    __tablename__ = "zoning_districts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    zone_code = Column(String(50), nullable=False, index=True)
    zone_name = Column(String(255))
    zone_description = Column(Text)
    
    # Geometry
    geometry = Column(Geometry('MULTIPOLYGON', srid=4326))
    
    # Source metadata
    source_updated_at = Column(DateTime(timezone=True))
    ingested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    raw_data = Column(JSON)
    
    __table_args__ = (
        Index('idx_zoning_geom', 'geometry', postgresql_using='gist'),
    )


class CityLimit(Base):
    """
    City limits (Baker, Baton Rouge, Central, Zachary).
    """
    __tablename__ = "city_limits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    city_name = Column(String(100), nullable=False, index=True)
    city_code = Column(String(20))
    
    # Geometry
    geometry = Column(Geometry('MULTIPOLYGON', srid=4326))
    
    # Source metadata
    source_updated_at = Column(DateTime(timezone=True))
    ingested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    raw_data = Column(JSON)
    
    __table_args__ = (
        Index('idx_city_limits_geom', 'geometry', postgresql_using='gist'),
    )


class AdjudicatedParcel(Base):
    """
    Adjudicated parcels (tax-foreclosed properties).
    """
    __tablename__ = "adjudicated_parcels"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    parcel_uid = Column(String(64), nullable=False, index=True)
    parcel_id = Column(String(100), index=True)
    
    # Adjudication details
    adjudication_date = Column(DateTime(timezone=True))
    judgment_year = Column(Integer)
    status = Column(String(100))
    
    # Property info
    owner_name = Column(String(512))
    site_address = Column(String(512))
    
    # Geometry
    geometry = Column(Geometry('POLYGON', srid=4326))
    
    # Source metadata
    source_updated_at = Column(DateTime(timezone=True))
    ingested_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    raw_data = Column(JSON)
    
    __table_args__ = (
        Index('idx_adjudicated_geom', 'geometry', postgresql_using='gist'),
    )

