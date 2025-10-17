"""
Data catalog models for tracking data sources and freshness.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    JSON,
    Boolean,
    Text,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum

from app.core.database import Base


class DataSourceType(str, enum.Enum):
    """Types of data sources."""

    SOCRATA = "socrata"
    ARCGIS = "arcgis"
    MANUAL = "manual"


class DataSourceStatus(str, enum.Enum):
    """Status of data source."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class DataCatalog(Base):
    """
    Catalog of all external data sources with freshness tracking.
    """

    __tablename__ = "data_catalog"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type = Column(SQLEnum(DataSourceType), nullable=False)
    source_name = Column(String(255), nullable=False, unique=True)
    dataset_id = Column(String(255), nullable=False)
    endpoint = Column(Text, nullable=False)

    # Freshness tracking
    last_seen_updated_at = Column(DateTime(timezone=True))
    last_ingest_at = Column(DateTime(timezone=True))
    last_successful_ingest_at = Column(DateTime(timezone=True))

    # Data characteristics
    schema_hash = Column(String(64))
    row_count = Column(Integer, default=0)

    # Status
    status = Column(SQLEnum(DataSourceStatus), default=DataSourceStatus.HEALTHY)
    consecutive_failures = Column(Integer, default=0)
    last_error = Column(Text)

    # Metadata
    ingest_job_id = Column(String(255))
    metadata = Column(JSON)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class DataSource(Base):
    """
    Configuration for data sources.
    """

    __tablename__ = "data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    type = Column(SQLEnum(DataSourceType), nullable=False)

    # Connection details
    base_url = Column(String(512), nullable=False)
    dataset_id = Column(String(255))
    service_path = Column(String(512))

    # Sync configuration
    sync_enabled = Column(Boolean, default=True)
    sync_interval_hours = Column(Integer, default=24)
    fields_to_index = Column(JSON)  # List of field names

    # Credentials (encrypted)
    api_key = Column(String(512))

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class DataQualityCheck(Base):
    """
    Data quality check results.
    """

    __tablename__ = "data_quality_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    catalog_id = Column(UUID(as_uuid=True), nullable=False)

    check_name = Column(String(255), nullable=False)
    check_type = Column(String(100))  # uniqueness, non_null, geometry_valid, etc.

    passed = Column(Boolean, nullable=False)
    result = Column(JSON)
    error_message = Column(Text)

    checked_at = Column(DateTime(timezone=True), default=datetime.utcnow)
