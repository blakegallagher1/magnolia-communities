"""
Unit tests for the underwriting autopilot service.
"""

import pytest

from app.schemas.underwriting import (
    ExpenseLine,
    UnderwritingAssumptions,
    UnderwritingLoanTerms,
    UnderwritingPropertyProfile,
    UnderwritingRunRequest,
    T12Financials,
    UnderwritingVerdict,
)
from app.services.underwriting_autopilot import UnderwritingAutopilotService


def _build_sample_request() -> UnderwritingRunRequest:
    """Helper to build a representative underwriting payload."""
    property_profile = UnderwritingPropertyProfile(
        name="Magnolia Terrace",
        address="123 Oak St, Baton Rouge, LA",
        units=40,
        occupancy_rate=0.9,
        average_rent=500.0,
        purchase_price=1_800_000.0,
    )
    loan_terms = UnderwritingLoanTerms(
        loan_amount=1_350_000.0,
        interest_rate=0.065,
        amortization_years=25,
        term_years=10,
    )
    t12 = T12Financials(
        gross_potential_rent=240_000.0,
        vacancy_loss=20_000.0,
        other_income=12_000.0,
        operating_expenses=[
            ExpenseLine(category="repairs", amount=45_000.0),
            ExpenseLine(category="utilities", amount=25_000.0),
            ExpenseLine(category="taxes", amount=10_000.0),
            ExpenseLine(category="insurance", amount=10_000.0),
        ],
        capital_reserves=12_000.0,
        management_fee_rate=0.04,
        include_management_fee=True,
    )
    assumptions = UnderwritingAssumptions(
        rent_growth=0.03,
        expense_growth=0.025,
        stabilized_occupancy=0.95,
        stabilization_years=3,
        exit_cap_rate=0.065,
        exit_year=10,
        downside_vacancy_delta=0.10,
        downside_expense_increase=0.15,
        upside_rent_growth=0.03,
        interest_rate_shock=0.02,
        major_capex_amount=150_000.0,
    )

    return UnderwritingRunRequest(
        property=property_profile,
        loan=loan_terms,
        t12=t12,
        assumptions=assumptions,
    )


@pytest.mark.asyncio
async def test_underwriting_autopilot_base_case_metrics():
    """Base case produces expected NOI, DSCR, and cap rate."""
    service = UnderwritingAutopilotService()
    payload = _build_sample_request()

    result = await service.run(payload)
    metrics = result.base_case.metrics

    assert pytest.approx(metrics.effective_gross_income, rel=1e-4) == 232_000.0
    assert pytest.approx(metrics.noi, rel=1e-4) == 132_720.0
    assert pytest.approx(metrics.cap_rate, rel=1e-4) == 132_720.0 / 1_800_000.0
    assert pytest.approx(metrics.dscr, rel=1e-4) == 1.2133
    assert metrics.annual_debt_service > 0
    assert result.projection.irr is not None


@pytest.mark.asyncio
async def test_underwriting_autopilot_stress_cases():
    """Stress tests respond to changing assumptions."""
    service = UnderwritingAutopilotService()
    payload = _build_sample_request()

    result = await service.run(payload)

    stress_names = {scenario.name for scenario in result.stress_tests}
    assert {"Downside Case", "Upside Case", "Interest Rate Shock", "Major Capex Hit"} == stress_names

    capex_scenario = next(
        scenario for scenario in result.stress_tests if scenario.name == "Major Capex Hit"
    )
    assert capex_scenario.metrics.net_cash_flow < result.base_case.metrics.net_cash_flow
    assert capex_scenario.metrics.net_cash_flow <= result.base_case.metrics.net_cash_flow - 150_000


@pytest.mark.asyncio
async def test_underwriting_autopilot_recommendation_verdict():
    """Recommendation verdict aligns with metric thresholds."""
    service = UnderwritingAutopilotService()
    payload = _build_sample_request()

    # Push leverage higher to degrade DSCR & cash-on-cash.
    payload = payload.model_copy(
        update={
            "loan": payload.loan.model_copy(update={"loan_amount": 1_440_000.0}),
        }
    )

    result = await service.run(payload)
    assert result.recommendation.verdict in {
        UnderwritingVerdict.YELLOW,
        UnderwritingVerdict.RED,
    }
