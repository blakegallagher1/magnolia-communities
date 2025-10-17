"""
Financial screening and scenario modeling endpoints.
"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.financial_screening import FinancialScreeningService

router = APIRouter()


class ScenarioInputs(BaseModel):
    """Input schema for financial scenario."""

    purchase_price: float = Field(..., gt=0)
    pad_count: int = Field(..., gt=0)
    current_rent: float = Field(..., gt=0)
    occupancy_rate: float = Field(..., ge=0, le=1)
    operating_expenses: float = Field(..., ge=0)
    property_tax: float = Field(..., ge=0)
    insurance: float = Field(..., ge=0)
    loan_ltv: float = Field(0.75, ge=0, le=1)
    interest_rate: float = Field(0.07, gt=0, lt=0.5)
    term_years: int = Field(30, gt=0, le=50)


class BuyBoxCriteria(BaseModel):
    """Buy-box criteria for evaluation."""

    min_dscr: float = Field(1.25, gt=0)
    min_debt_yield: float = Field(0.10, gt=0)
    min_cap_rate: float = Field(0.08, gt=0)
    max_price_per_pad: float = Field(15000, gt=0)


class ProFormaRequest(BaseModel):
    """Request schema for pro forma generation."""

    scenario: ScenarioInputs
    projection_years: int = Field(5, ge=1, le=20)
    rent_growth: float = Field(0.03, ge=-0.1, le=0.2)
    expense_growth: float = Field(0.025, ge=-0.1, le=0.2)
    exit_cap_rate: Optional[float] = Field(None, gt=0, lt=0.5)


@router.post("/scenario/base")
async def calculate_base_scenario(
    inputs: ScenarioInputs,
):
    """
    Calculate base case financial scenario.

    Returns comprehensive analysis including:
    - Revenue breakdown (gross income, vacancy, EGI)
    - Expense breakdown and ratios
    - NOI calculation
    - Financing structure
    - Key metrics (Cap Rate, DSCR, Debt Yield, CoC)
    """
    service = FinancialScreeningService()

    scenario = service.build_base_scenario(
        purchase_price=inputs.purchase_price,
        pad_count=inputs.pad_count,
        current_rent=inputs.current_rent,
        occupancy_rate=inputs.occupancy_rate,
        operating_expenses=inputs.operating_expenses,
        property_tax=inputs.property_tax,
        insurance=inputs.insurance,
        loan_ltv=inputs.loan_ltv,
        interest_rate=inputs.interest_rate,
        term_years=inputs.term_years,
    )

    return scenario


@router.post("/scenario/stress")
async def run_stress_scenarios(
    inputs: ScenarioInputs,
):
    """
    Run comprehensive stress test scenarios.

    Stress scenarios include:
    - Rent decreases: -$10, -$25, -$50/month
    - Occupancy drops: 85%, 80%, 70%
    - Expense increases: +10%, +20%, +30%
    - Rate increases: +100bps, +200bps
    """
    service = FinancialScreeningService()

    # First build base scenario
    base_scenario = service.build_base_scenario(
        purchase_price=inputs.purchase_price,
        pad_count=inputs.pad_count,
        current_rent=inputs.current_rent,
        occupancy_rate=inputs.occupancy_rate,
        operating_expenses=inputs.operating_expenses,
        property_tax=inputs.property_tax,
        insurance=inputs.insurance,
        loan_ltv=inputs.loan_ltv,
        interest_rate=inputs.interest_rate,
        term_years=inputs.term_years,
    )

    # Run stress tests
    stress_scenarios = service.run_stress_scenarios(base_scenario)

    return {
        "base_scenario": base_scenario,
        "stress_scenarios": stress_scenarios,
    }


@router.post("/buy-box/evaluate")
async def evaluate_buy_box(
    inputs: ScenarioInputs,
    criteria: BuyBoxCriteria = BuyBoxCriteria(),
):
    """
    Evaluate scenario against buy-box criteria.

    Returns pass/fail verdict with detailed breakdown of each criterion.
    """
    service = FinancialScreeningService()

    scenario = service.build_base_scenario(
        purchase_price=inputs.purchase_price,
        pad_count=inputs.pad_count,
        current_rent=inputs.current_rent,
        occupancy_rate=inputs.occupancy_rate,
        operating_expenses=inputs.operating_expenses,
        property_tax=inputs.property_tax,
        insurance=inputs.insurance,
        loan_ltv=inputs.loan_ltv,
        interest_rate=inputs.interest_rate,
        term_years=inputs.term_years,
    )

    evaluation = service.evaluate_buy_box(
        scenario=scenario,
        min_dscr=criteria.min_dscr,
        min_debt_yield=criteria.min_debt_yield,
        min_cap_rate=criteria.min_cap_rate,
        max_price_per_pad=criteria.max_price_per_pad,
    )

    return {
        "scenario": scenario,
        "buy_box_evaluation": evaluation,
    }


@router.post("/pro-forma")
async def generate_pro_forma(
    request: ProFormaRequest,
):
    """
    Generate multi-year pro forma with projections and IRR.

    Includes:
    - Annual projections with rent/expense growth
    - Exit valuation
    - Cash flow analysis
    - IRR calculation
    """
    service = FinancialScreeningService()

    # Build base scenario
    base_scenario = service.build_base_scenario(
        purchase_price=request.scenario.purchase_price,
        pad_count=request.scenario.pad_count,
        current_rent=request.scenario.current_rent,
        occupancy_rate=request.scenario.occupancy_rate,
        operating_expenses=request.scenario.operating_expenses,
        property_tax=request.scenario.property_tax,
        insurance=request.scenario.insurance,
        loan_ltv=request.scenario.loan_ltv,
        interest_rate=request.scenario.interest_rate,
        term_years=request.scenario.term_years,
    )

    # Generate pro forma
    pro_forma = service.generate_pro_forma(
        base_scenario=base_scenario,
        projection_years=request.projection_years,
        rent_growth=request.rent_growth,
        expense_growth=request.expense_growth,
        exit_cap_rate=request.exit_cap_rate,
    )

    return {
        "base_scenario": base_scenario,
        "pro_forma": pro_forma,
    }


@router.post("/quick-screen")
async def quick_financial_screen(
    inputs: ScenarioInputs,
    criteria: BuyBoxCriteria = BuyBoxCriteria(),
):
    """
    Comprehensive quick screen including:
    - Base scenario
    - Stress scenarios
    - Buy-box evaluation
    - 5-year pro forma

    One-stop endpoint for complete deal analysis.
    """
    service = FinancialScreeningService()

    # Base scenario
    base_scenario = service.build_base_scenario(
        purchase_price=inputs.purchase_price,
        pad_count=inputs.pad_count,
        current_rent=inputs.current_rent,
        occupancy_rate=inputs.occupancy_rate,
        operating_expenses=inputs.operating_expenses,
        property_tax=inputs.property_tax,
        insurance=inputs.insurance,
        loan_ltv=inputs.loan_ltv,
        interest_rate=inputs.interest_rate,
        term_years=inputs.term_years,
    )

    # Stress scenarios
    stress_scenarios = service.run_stress_scenarios(base_scenario)

    # Buy-box evaluation
    buy_box = service.evaluate_buy_box(
        scenario=base_scenario,
        min_dscr=criteria.min_dscr,
        min_debt_yield=criteria.min_debt_yield,
        min_cap_rate=criteria.min_cap_rate,
        max_price_per_pad=criteria.max_price_per_pad,
    )

    # Pro forma
    pro_forma = service.generate_pro_forma(
        base_scenario=base_scenario,
        projection_years=5,
    )

    return {
        "base_scenario": base_scenario,
        "stress_scenarios": stress_scenarios[:5],  # Top 5 stress tests
        "buy_box_evaluation": buy_box,
        "pro_forma": pro_forma,
        "recommendation": ("PASS" if buy_box["passes_buy_box"] else "FAIL"),
    }
