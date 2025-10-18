"""
Integration test for the underwriting autopilot API endpoint.
"""

import pytest


@pytest.mark.asyncio
async def test_underwriting_run_endpoint(api_client):
    """POST /api/v1/underwriting/run returns underwriting analysis."""
    payload = {
        "property": {
            "name": "Magnolia Terrace",
            "address": "123 Oak St, Baton Rouge, LA",
            "city": "Baton Rouge",
            "state": "LA",
            "zip_code": "70802",
            "units": 40,
            "occupancy_rate": 0.9,
            "average_rent": 500.0,
            "purchase_price": 1_800_000.0,
        },
        "loan": {
            "loan_amount": 1_350_000.0,
            "interest_rate": 0.065,
            "amortization_years": 25,
            "term_years": 10,
        },
        "t12": {
            "gross_potential_rent": 240_000.0,
            "vacancy_loss": 20_000.0,
            "credit_loss": 0.0,
            "concessions": 0.0,
            "other_income": 12_000.0,
            "operating_expenses": [
                {"category": "repairs", "amount": 45_000.0},
                {"category": "utilities", "amount": 25_000.0},
                {"category": "taxes", "amount": 10_000.0},
                {"category": "insurance", "amount": 10_000.0},
            ],
            "capital_reserves": 12_000.0,
            "management_fee_rate": 0.04,
            "include_management_fee": True,
        },
        "assumptions": {
            "rent_growth": 0.03,
            "expense_growth": 0.025,
            "stabilized_occupancy": 0.95,
            "stabilization_years": 3,
            "exit_cap_rate": 0.065,
            "exit_year": 10,
            "downside_vacancy_delta": 0.10,
            "downside_expense_increase": 0.15,
            "upside_rent_growth": 0.03,
            "interest_rate_shock": 0.02,
            "major_capex_amount": 150_000.0,
        },
    }

    response = await api_client.post("/api/v1/underwriting/run", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["base_case"]["metrics"]["noi"] > 0
    assert data["base_case"]["metrics"]["dscr"] > 0
    assert data["recommendation"]["verdict"] in {"GREEN", "YELLOW", "RED"}
    assert len(data["stress_tests"]) == 4
    assert data["projection"]["sale_year"] == 10
