"""
Financial models for loans, insurance, rent rolls, and scenarios.
"""
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Integer, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.database import Base


class Loan(Base):
    """
    Loan financing information.
    """
    __tablename__ = "loans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference
    deal_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    park_id = Column(UUID(as_uuid=True), index=True)
    
    # Lender
    lender_name = Column(String(255))
    lender_contact = Column(String(255))
    
    # Loan terms
    loan_amount = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False)  # as decimal (e.g., 0.065 for 6.5%)
    term_months = Column(Integer, nullable=False)
    amortization_months = Column(Integer)
    
    # Payments
    monthly_payment = Column(Float)
    annual_debt_service = Column(Float)
    
    # Underwriting metrics
    ltv = Column(Float)  # Loan-to-Value
    dscr = Column(Float)  # Debt Service Coverage Ratio
    debt_yield = Column(Float)
    
    # Dates
    application_date = Column(DateTime(timezone=True))
    approval_date = Column(DateTime(timezone=True))
    funding_date = Column(DateTime(timezone=True))
    maturity_date = Column(DateTime(timezone=True))
    
    # Status
    status = Column(String(50))  # applied, approved, funded, closed
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Insurance(Base):
    """
    Insurance policies for parks.
    """
    __tablename__ = "insurance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference
    park_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Carrier
    carrier_name = Column(String(255), nullable=False)
    policy_number = Column(String(100))
    
    # Coverage
    policy_type = Column(String(100))  # property, liability, flood, wind, etc.
    coverage_amount = Column(Float)
    deductible = Column(Float)
    
    # Premium
    annual_premium = Column(Float, nullable=False)
    
    # Dates
    effective_date = Column(DateTime(timezone=True), nullable=False)
    expiration_date = Column(DateTime(timezone=True), nullable=False)
    renewal_date = Column(DateTime(timezone=True))
    
    # Status
    status = Column(String(50))  # quote, bound, active, expired, cancelled
    
    # Metadata
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RentRoll(Base):
    """
    Rent roll snapshots for parks.
    """
    __tablename__ = "rent_rolls"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference
    park_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Snapshot date
    snapshot_date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Aggregates
    total_pads = Column(Integer, nullable=False)
    occupied_pads = Column(Integer, nullable=False)
    vacant_pads = Column(Integer)
    occupancy_rate = Column(Float)
    
    # Revenue
    total_rent = Column(Float)
    average_rent = Column(Float)
    
    # Detailed roll (JSON array)
    pad_details = Column(JSON)  # [{pad_num, tenant, rent, lease_start, lease_end}]
    
    # Metadata
    source = Column(String(50))  # upload, manual, system
    uploaded_by = Column(String(255))
    notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class Scenario(Base):
    """
    Financial scenario modeling for underwriting.
    """
    __tablename__ = "scenarios"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference
    deal_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Scenario identification
    name = Column(String(255), nullable=False)
    scenario_type = Column(String(50))  # base, optimistic, pessimistic, stress
    
    # Input assumptions
    purchase_price = Column(Float, nullable=False)
    pad_count = Column(Integer, nullable=False)
    
    # Revenue assumptions
    current_rent = Column(Float, nullable=False)
    projected_rent = Column(Float)
    rent_increase_pct = Column(Float)
    occupancy_rate = Column(Float, nullable=False)
    
    # Expense assumptions
    operating_expenses = Column(Float)
    expense_ratio = Column(Float)
    capex_reserve = Column(Float)
    property_tax = Column(Float)
    insurance = Column(Float)
    
    # Financing assumptions
    loan_amount = Column(Float)
    interest_rate = Column(Float)
    term_months = Column(Integer)
    
    # Calculated outputs
    gross_income = Column(Float)
    effective_gross_income = Column(Float)
    noi = Column(Float)
    annual_debt_service = Column(Float)
    cash_flow = Column(Float)
    
    # Metrics
    cap_rate = Column(Float)
    dscr = Column(Float)
    debt_yield = Column(Float)
    cash_on_cash = Column(Float)
    irr = Column(Float)
    value_per_pad = Column(Float)
    
    # Exit assumptions
    exit_year = Column(Integer)
    exit_cap_rate = Column(Float)
    exit_value = Column(Float)
    
    # Buy-box verdict
    passes_buy_box = Column(Integer)  # store as 0/1 to avoid unused Boolean import
    buy_box_notes = Column(Text)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

