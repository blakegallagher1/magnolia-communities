"""
Tests for financial screening service.
"""
import pytest
from app.services.financial_screening import FinancialScreeningService


class TestFinancialScreening:
    """Test financial screening calculations."""
    
    @pytest.fixture
    def service(self):
        return FinancialScreeningService()
    
    def test_calculate_noi(self, service):
        """Test NOI calculation."""
        gross_income = 120000
        vacancy_loss = 6000  # 5%
        operating_expenses = 40000
        
        noi = service.calculate_noi(gross_income, vacancy_loss, operating_expenses)
        
        assert noi == 74000  # 120000 - 6000 - 40000
    
    def test_calculate_dscr(self, service):
        """Test DSCR calculation."""
        noi = 74000
        annual_debt_service = 55000
        
        dscr = service.calculate_dscr(noi, annual_debt_service)
        
        assert pytest.approx(dscr, 0.01) == 1.345
    
    def test_calculate_debt_yield(self, service):
        """Test debt yield calculation."""
        noi = 74000
        loan_amount = 600000
        
        debt_yield = service.calculate_debt_yield(noi, loan_amount)
        
        assert pytest.approx(debt_yield, 0.001) == 0.123
    
    def test_calculate_cap_rate(self, service):
        """Test cap rate calculation."""
        noi = 74000
        property_value = 800000
        
        cap_rate = service.calculate_cap_rate(noi, property_value)
        
        assert pytest.approx(cap_rate, 0.001) == 0.0925
    
    def test_base_scenario(self, service):
        """Test base scenario generation."""
        scenario = service.build_base_scenario(
            purchase_price=800000,
            pad_count=40,
            current_rent=250,
            occupancy_rate=0.90,
            operating_expenses=35000,
            property_tax=8000,
            insurance=4000,
            loan_ltv=0.75,
            interest_rate=0.07,
            term_years=30,
        )
        
        # Check revenue
        assert scenario["revenue"]["gross_income"] == 120000  # 40 * 250 * 12
        assert scenario["revenue"]["vacancy_loss"] == 12000  # 10% vacancy
        assert scenario["revenue"]["egi"] == 108000
        
        # Check NOI
        assert scenario["noi"] == 61000  # 108000 - 47000
        
        # Check metrics
        assert scenario["metrics"]["cap_rate"] > 0
        assert scenario["metrics"]["dscr"] > 0
        assert scenario["metrics"]["debt_yield"] > 0
        assert scenario["metrics"]["value_per_pad"] == 20000
    
    def test_stress_scenarios(self, service):
        """Test stress scenario generation."""
        base_scenario = service.build_base_scenario(
            purchase_price=800000,
            pad_count=40,
            current_rent=250,
            occupancy_rate=0.90,
            operating_expenses=35000,
            property_tax=8000,
            insurance=4000,
        )
        
        stress_scenarios = service.run_stress_scenarios(base_scenario)
        
        # Should generate multiple stress tests
        assert len(stress_scenarios) > 0
        
        # Check scenario types
        scenario_types = {s["type"] for s in stress_scenarios}
        assert "rent_stress" in scenario_types
        assert "occupancy_stress" in scenario_types
        assert "expense_stress" in scenario_types
        assert "rate_stress" in scenario_types
    
    def test_buy_box_evaluation(self, service):
        """Test buy-box evaluation."""
        # Good deal scenario
        good_scenario = service.build_base_scenario(
            purchase_price=500000,
            pad_count=40,
            current_rent=250,
            occupancy_rate=0.95,
            operating_expenses=30000,
            property_tax=5000,
            insurance=3000,
        )
        
        evaluation = service.evaluate_buy_box(good_scenario)
        
        assert "passes_buy_box" in evaluation
        assert "criteria" in evaluation
        assert "dscr_check" in evaluation["criteria"]
        assert "debt_yield_check" in evaluation["criteria"]
        assert "cap_rate_check" in evaluation["criteria"]
        assert "price_per_pad_check" in evaluation["criteria"]
    
    def test_pro_forma_generation(self, service):
        """Test pro forma generation with IRR."""
        base_scenario = service.build_base_scenario(
            purchase_price=800000,
            pad_count=40,
            current_rent=250,
            occupancy_rate=0.90,
            operating_expenses=35000,
            property_tax=8000,
            insurance=4000,
        )
        
        pro_forma = service.generate_pro_forma(
            base_scenario=base_scenario,
            projection_years=5,
            rent_growth=0.03,
            expense_growth=0.025,
        )
        
        assert len(pro_forma["years"]) == 5
        assert "irr" in pro_forma
        assert len(pro_forma["cash_flows"]) == 6  # Initial + 5 years
        
        # First cash flow should be negative (initial investment)
        assert pro_forma["cash_flows"][0] < 0
    
    def test_irr_calculation(self, service):
        """Test IRR calculation."""
        # Simple cash flows
        cash_flows = [-100000, 10000, 15000, 20000, 25000, 150000]
        
        irr = service.calculate_irr(cash_flows)
        
        assert irr is not None
        assert irr > 0  # Should be positive return
        assert irr < 1  # Should be less than 100%

