"""Agent-related persistence models."""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Float,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class ParcelHunterRun(Base):
    """Execution record for Parcel Hunter agent runs."""

    __tablename__ = "parcel_hunter_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(32), default="running", nullable=False)
    total_candidates = Column(Integer, default=0, nullable=False)
    leads_created = Column(Integer, default=0, nullable=False)
    run_metadata = Column(JSON)


class ParcelHunterResult(Base):
    """Candidate parcels evaluated during a Parcel Hunter run."""

    __tablename__ = "parcel_hunter_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("parcel_hunter_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    parcel_uid = Column(String(64), nullable=False)
    parcel_id = Column(String(100))
    site_address = Column(String(512))
    owner_name = Column(String(512))
    municipality = Column(String(100))
    parcel_acres = Column(Float)
    estimated_units = Column(Integer)
    complaints_per_unit = Column(Float)
    annual_complaints = Column(Float)
    flood_risk = Column(String(50))
    recommendation = Column(String(20), nullable=False)
    score = Column(Integer, nullable=False)
    reasoning = Column(String(1024))
    context = Column(JSON)
    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "run_id", "parcel_uid", name="uq_parcel_hunter_result_parcel_run"
        ),
        Index("idx_parcel_hunter_result_parcel", "parcel_uid"),
        Index("idx_parcel_hunter_result_score", "score"),
    )
