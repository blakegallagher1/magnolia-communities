"""
Pydantic schemas for the underwriting autopilot service.

These schemas capture the payloads exchanged by the underwriting API as well as
the structured results returned to clients. They are intentionally verbose so
that downstream consumers (frontend, reporting, other agents) can rely on
stable field names with explicit semantics.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ExpenseLine(BaseModel):
    """Single T12 operating expense line item."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., ge=0, description="Annual expense amount in USD")


class T12Financials(BaseModel):
    """Trailing-twelve-month income statement used for underwriting."""

    model_config = ConfigDict(extra="forbid")

    gross_potential_rent: float = Field(..., ge=0)
    vacancy_loss: float = Field(0.0, ge=0)
    credit_loss: float = Field(0.0, ge=0, description="Bad debt write-offs")
    concessions: float = Field(
        0.0,
        ge=0,
        description="Free rent or move-in concessions deducted from rent",
    )
    other_income: float = Field(0.0, ge=0, description="Ancillary income streams")
    operating_expenses: List[ExpenseLine] = Field(default_factory=list)
    capital_reserves: float = Field(
        0.0,
        ge=0,
        description="Annual reserve for replacements included in underwriting",
    )
    management_fee_rate: float = Field(
        0.0,
        ge=0,
        le=0.15,
        description="Optional property management fee computed as % of EGI",
    )
    include_management_fee: bool = Field(
        False,
        description="If True, apply management_fee_rate to EGI and add to expenses",
    )

    def total_operating_expenses(self, effective_gross_income: float | None = None) -> float:
        """
        Compute total operating expenses, optionally adding management fees.

        Args:
            effective_gross_income: Optional EGI used to derive the management fee.
        """
        base = sum(item.amount for item in self.operating_expenses)
        if self.include_management_fee and effective_gross_income:
            base += effective_gross_income * self.management_fee_rate
        return base


class UnderwritingPropertyProfile(BaseModel):
    """Core property assumptions that drive underwriting outputs."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    address: Optional[str] = Field(None, max_length=512)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=2)
    zip_code: Optional[str] = Field(None, max_length=10)
    units: int = Field(..., gt=0)
    occupancy_rate: float = Field(..., ge=0, le=1)
    average_rent: float = Field(..., ge=0)
    purchase_price: float = Field(..., gt=0)


class UnderwritingLoanTerms(BaseModel):
    """Debt assumptions used to derive debt service and leverage metrics."""

    model_config = ConfigDict(extra="forbid")

    loan_amount: Optional[float] = Field(None, ge=0)
    loan_to_value: Optional[float] = Field(None, ge=0, le=1)
    interest_rate: float = Field(..., gt=0, lt=1)
    amortization_years: int = Field(..., ge=1, le=40)
    term_years: int = Field(..., ge=1, le=40)


class UnderwritingAssumptions(BaseModel):
    """Forward-looking assumptions for the 10-year projection."""

    model_config = ConfigDict(extra="forbid")

    rent_growth: float = Field(0.03, ge=-0.1, le=0.25)
    expense_growth: float = Field(0.025, ge=-0.1, le=0.2)
    stabilized_occupancy: float = Field(0.95, ge=0, le=1)
    stabilization_years: int = Field(3, ge=1, le=10)
    exit_cap_rate: float = Field(0.065, gt=0, lt=0.25)
    exit_year: int = Field(10, ge=1, le=30)
    downside_vacancy_delta: float = Field(0.10, ge=0, le=0.5)
    downside_expense_increase: float = Field(0.15, ge=0, le=1)
    upside_rent_growth: float = Field(0.03, ge=-0.1, le=0.25)
    interest_rate_shock: float = Field(0.02, ge=0, le=0.05)
    major_capex_amount: float = Field(150_000.0, ge=0)


class UnderwritingRunRequest(BaseModel):
    """Payload accepted by the underwriting autopilot endpoint."""

    model_config = ConfigDict(extra="forbid")

    deal_id: Optional[UUID] = Field(
        None, description="Existing deal identifier for enrichment (optional)"
    )
    property: UnderwritingPropertyProfile
    loan: UnderwritingLoanTerms
    t12: T12Financials
    assumptions: UnderwritingAssumptions = Field(default_factory=UnderwritingAssumptions)


class UnderwritingVerdict(str, Enum):
    """Verdict tiers used to describe underwriting confidence."""

    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class UnderwritingMetricSummary(BaseModel):
    """Calculated headline metrics for a scenario."""

    model_config = ConfigDict(extra="forbid")

    effective_gross_income: float
    noi: float
    operating_expenses: float
    operating_expense_ratio: float
    cap_rate: float
    dscr: float
    debt_yield: float
    cash_on_cash: float
    annual_debt_service: float
    loan_to_value: float
    equity: float
    net_cash_flow: float
    breakeven_occupancy: float
    occupancy: float


class UnderwritingScenarioResult(BaseModel):
    """Result for the base case or a named stress scenario."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    assumptions: Dict[str, float]
    metrics: UnderwritingMetricSummary
    classification: UnderwritingVerdict
    modeled_irr: Optional[float] = Field(
        None, description="If supplied, IRR associated with this scenario"
    )


class UnderwritingProjectionYear(BaseModel):
    """Detailed annual projection output."""

    model_config = ConfigDict(extra="forbid")

    year: int
    occupancy: float
    gross_potential_rent: float
    other_income: float
    vacancy_loss: float
    effective_gross_income: float
    operating_expenses: float
    noi: float
    annual_debt_service: float
    capital_reserves: float
    net_cash_flow: float
    ending_loan_balance: float


class UnderwritingProjectionSummary(BaseModel):
    """Summary of the 10-year plan including equity returns."""

    model_config = ConfigDict(extra="forbid")

    years: List[UnderwritingProjectionYear]
    irr: Optional[float]
    equity_multiple: Optional[float]
    cash_flows: List[float]
    exit_value: float
    exit_proceeds: float
    sale_year: int


class UnderwritingDealSummary(BaseModel):
    """Context about the deal/property that was evaluated."""

    model_config = ConfigDict(extra="forbid")

    deal_id: Optional[UUID]
    property_name: str
    address: Optional[str]
    units: int
    occupancy_rate: float
    purchase_price: float
    loan_amount: float
    equity: float
    loan_to_value: float


class UnderwritingRecommendation(BaseModel):
    """Final recommendation with rationale and key call-outs."""

    model_config = ConfigDict(extra="forbid")

    verdict: UnderwritingVerdict
    rationale: str
    highlights: List[str]
    risks: List[str]
    irr: Optional[float]
    cash_on_cash: float
    dscr: float
    cap_rate: float


class UnderwritingRunResponse(BaseModel):
    """Full response returned by the underwriting autopilot endpoint."""

    model_config = ConfigDict(extra="forbid")

    deal_summary: UnderwritingDealSummary
    base_case: UnderwritingScenarioResult
    stress_tests: List[UnderwritingScenarioResult]
    projection: UnderwritingProjectionSummary
    recommendation: UnderwritingRecommendation
