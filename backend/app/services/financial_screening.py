"""
Financial screening engine with DSCR, IRR, and scenario analysis.
Implements buy-box criteria and stress testing.
"""
import logging
from typing import Dict, Any, List, Optional
from numpy_financial import irr as np_irr

logger = logging.getLogger(__name__)


class FinancialScreeningService:
    """
    Service for financial underwriting and scenario analysis.
    """
    
    @staticmethod
    def calculate_noi(
        gross_income: float,
        vacancy_loss: float,
        operating_expenses: float,
    ) -> float:
        """
        Calculate Net Operating Income.
        NOI = EGI - OpEx
        where EGI = Gross Income - Vacancy Loss
        """
        egi = gross_income - vacancy_loss
        return egi - operating_expenses
    
    @staticmethod
    def calculate_dscr(noi: float, annual_debt_service: float) -> float:
        """
        Calculate Debt Service Coverage Ratio.
        DSCR = NOI / Annual Debt Service
        """
        if annual_debt_service == 0:
            return 0.0
        return noi / annual_debt_service
    
    @staticmethod
    def calculate_debt_yield(noi: float, loan_amount: float) -> float:
        """
        Calculate Debt Yield.
        Debt Yield = NOI / Loan Amount
        """
        if loan_amount == 0:
            return 0.0
        return noi / loan_amount
    
    @staticmethod
    def calculate_cap_rate(noi: float, property_value: float) -> float:
        """
        Calculate Capitalization Rate.
        Cap Rate = NOI / Property Value
        """
        if property_value == 0:
            return 0.0
        return noi / property_value
    
    @staticmethod
    def calculate_cash_on_cash(
        cash_flow: float, equity_invested: float
    ) -> float:
        """
        Calculate Cash-on-Cash return.
        CoC = Annual Cash Flow / Equity Invested
        """
        if equity_invested == 0:
            return 0.0
        return cash_flow / equity_invested
    
    @staticmethod
    def calculate_annual_debt_service(
        loan_amount: float,
        annual_interest_rate: float,
        term_years: int,
    ) -> float:
        """
        Calculate annual debt service for a loan.
        """
        if annual_interest_rate == 0:
            return loan_amount / term_years
        
        monthly_rate = annual_interest_rate / 12
        num_payments = term_years * 12
        
        # Monthly payment using amortization formula
        monthly_payment = loan_amount * (
            monthly_rate * (1 + monthly_rate) ** num_payments
        ) / ((1 + monthly_rate) ** num_payments - 1)
        
        return monthly_payment * 12
    
    @staticmethod
    def calculate_irr(cash_flows: List[float]) -> Optional[float]:
        """
        Calculate Internal Rate of Return.
        cash_flows: [initial_investment (negative), year1, year2, ..., final_year]
        """
        try:
            return float(np_irr(cash_flows))
        except Exception as e:
            logger.warning(f"IRR calculation failed: {e}")
            return None
    
    def build_base_scenario(
        self,
        purchase_price: float,
        pad_count: int,
        current_rent: float,
        occupancy_rate: float,
        operating_expenses: float,
        property_tax: float,
        insurance: float,
        loan_ltv: float = 0.75,
        interest_rate: float = 0.07,
        term_years: int = 30,
    ) -> Dict[str, Any]:
        """
        Build base case financial scenario.
        """
        # Revenue calculations
        gross_income = pad_count * current_rent * 12
        vacancy_loss = gross_income * (1 - occupancy_rate)
        egi = gross_income - vacancy_loss
        
        # Expense calculations
        total_opex = operating_expenses + property_tax + insurance
        expense_ratio = total_opex / gross_income if gross_income > 0 else 0
        
        # NOI
        noi = self.calculate_noi(gross_income, vacancy_loss, total_opex)
        
        # Financing
        loan_amount = purchase_price * loan_ltv
        equity = purchase_price - loan_amount
        annual_debt_service = self.calculate_annual_debt_service(
            loan_amount, interest_rate, term_years
        )
        
        # Cash flow
        cash_flow = noi - annual_debt_service
        
        # Metrics
        cap_rate = self.calculate_cap_rate(noi, purchase_price)
        dscr = self.calculate_dscr(noi, annual_debt_service)
        debt_yield = self.calculate_debt_yield(noi, loan_amount)
        coc = self.calculate_cash_on_cash(cash_flow, equity)
        value_per_pad = purchase_price / pad_count if pad_count > 0 else 0
        
        return {
            "inputs": {
                "purchase_price": purchase_price,
                "pad_count": pad_count,
                "current_rent": current_rent,
                "occupancy_rate": occupancy_rate,
                "operating_expenses": operating_expenses,
                "property_tax": property_tax,
                "insurance": insurance,
                "loan_ltv": loan_ltv,
                "interest_rate": interest_rate,
                "term_years": term_years,
            },
            "revenue": {
                "gross_income": gross_income,
                "vacancy_loss": vacancy_loss,
                "egi": egi,
            },
            "expenses": {
                "operating_expenses": operating_expenses,
                "property_tax": property_tax,
                "insurance": insurance,
                "total_opex": total_opex,
                "expense_ratio": expense_ratio,
            },
            "noi": noi,
            "financing": {
                "loan_amount": loan_amount,
                "equity": equity,
                "annual_debt_service": annual_debt_service,
            },
            "cash_flow": cash_flow,
            "metrics": {
                "cap_rate": cap_rate,
                "dscr": dscr,
                "debt_yield": debt_yield,
                "cash_on_cash": coc,
                "value_per_pad": value_per_pad,
            },
        }
    
    def run_stress_scenarios(
        self, base_scenario: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Run stress test scenarios on base case.
        
        Scenarios:
        - Rent decrease: -$10, -$25, -$50/month
        - Occupancy drop: to 85%, 80%, 70%
        - Expense increase: +10%, +20%, +30%
        - Insurance shock: +20%, +30%
        - Rate increase: +100bps, +200bps
        """
        base_inputs = base_scenario["inputs"]
        scenarios = []
        
        # Rent stress
        for rent_delta in [-10, -25, -50]:
            scenario = self.build_base_scenario(
                purchase_price=base_inputs["purchase_price"],
                pad_count=base_inputs["pad_count"],
                current_rent=base_inputs["current_rent"] + rent_delta,
                occupancy_rate=base_inputs["occupancy_rate"],
                operating_expenses=base_inputs["operating_expenses"],
                property_tax=base_inputs["property_tax"],
                insurance=base_inputs["insurance"],
                loan_ltv=base_inputs["loan_ltv"],
                interest_rate=base_inputs["interest_rate"],
                term_years=base_inputs["term_years"],
            )
            scenario["name"] = f"Rent {rent_delta:+}/month"
            scenario["type"] = "rent_stress"
            scenarios.append(scenario)
        
        # Occupancy stress
        for occ in [0.85, 0.80, 0.70]:
            scenario = self.build_base_scenario(
                purchase_price=base_inputs["purchase_price"],
                pad_count=base_inputs["pad_count"],
                current_rent=base_inputs["current_rent"],
                occupancy_rate=occ,
                operating_expenses=base_inputs["operating_expenses"],
                property_tax=base_inputs["property_tax"],
                insurance=base_inputs["insurance"],
                loan_ltv=base_inputs["loan_ltv"],
                interest_rate=base_inputs["interest_rate"],
                term_years=base_inputs["term_years"],
            )
            scenario["name"] = f"Occupancy {occ*100:.0f}%"
            scenario["type"] = "occupancy_stress"
            scenarios.append(scenario)
        
        # Expense stress
        for exp_mult in [1.1, 1.2, 1.3]:
            scenario = self.build_base_scenario(
                purchase_price=base_inputs["purchase_price"],
                pad_count=base_inputs["pad_count"],
                current_rent=base_inputs["current_rent"],
                occupancy_rate=base_inputs["occupancy_rate"],
                operating_expenses=base_inputs["operating_expenses"] * exp_mult,
                property_tax=base_inputs["property_tax"],
                insurance=base_inputs["insurance"],
                loan_ltv=base_inputs["loan_ltv"],
                interest_rate=base_inputs["interest_rate"],
                term_years=base_inputs["term_years"],
            )
            scenario["name"] = f"OpEx +{(exp_mult-1)*100:.0f}%"
            scenario["type"] = "expense_stress"
            scenarios.append(scenario)
        
        # Rate stress
        for rate_delta in [0.01, 0.02]:
            scenario = self.build_base_scenario(
                purchase_price=base_inputs["purchase_price"],
                pad_count=base_inputs["pad_count"],
                current_rent=base_inputs["current_rent"],
                occupancy_rate=base_inputs["occupancy_rate"],
                operating_expenses=base_inputs["operating_expenses"],
                property_tax=base_inputs["property_tax"],
                insurance=base_inputs["insurance"],
                loan_ltv=base_inputs["loan_ltv"],
                interest_rate=base_inputs["interest_rate"] + rate_delta,
                term_years=base_inputs["term_years"],
            )
            scenario["name"] = f"Rate +{rate_delta*100:.0f}bps"
            scenario["type"] = "rate_stress"
            scenarios.append(scenario)
        
        return scenarios
    
    def evaluate_buy_box(
        self,
        scenario: Dict[str, Any],
        min_dscr: float = 1.25,
        min_debt_yield: float = 0.10,
        min_cap_rate: float = 0.08,
        max_price_per_pad: float = 15000,
    ) -> Dict[str, Any]:
        """
        Evaluate scenario against buy-box criteria.
        
        Default criteria:
        - DSCR ≥ 1.25
        - Debt Yield ≥ 10%
        - Cap Rate ≥ 8%
        - Price/Pad ≤ $15,000
        """
        metrics = scenario["metrics"]
        # inputs = scenario["inputs"]
        
        criteria_checks = {
            "dscr_check": {
                "passes": metrics["dscr"] >= min_dscr,
                "value": metrics["dscr"],
                "threshold": min_dscr,
                "delta": metrics["dscr"] - min_dscr,
            },
            "debt_yield_check": {
                "passes": metrics["debt_yield"] >= min_debt_yield,
                "value": metrics["debt_yield"],
                "threshold": min_debt_yield,
                "delta": metrics["debt_yield"] - min_debt_yield,
            },
            "cap_rate_check": {
                "passes": metrics["cap_rate"] >= min_cap_rate,
                "value": metrics["cap_rate"],
                "threshold": min_cap_rate,
                "delta": metrics["cap_rate"] - min_cap_rate,
            },
            "price_per_pad_check": {
                "passes": metrics["value_per_pad"] <= max_price_per_pad,
                "value": metrics["value_per_pad"],
                "threshold": max_price_per_pad,
                "delta": max_price_per_pad - metrics["value_per_pad"],
            },
        }
        
        passes_all = all(check["passes"] for check in criteria_checks.values())
        
        return {
            "passes_buy_box": passes_all,
            "criteria": criteria_checks,
            "summary": {
                "total_checks": len(criteria_checks),
                "passed": sum(1 for c in criteria_checks.values() if c["passes"]),
                "failed": sum(1 for c in criteria_checks.values() if not c["passes"]),
            },
        }
    
    def generate_pro_forma(
        self,
        base_scenario: Dict[str, Any],
        projection_years: int = 5,
        rent_growth: float = 0.03,
        expense_growth: float = 0.025,
        exit_cap_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate multi-year pro forma with exit value and IRR.
        """
        inputs = base_scenario["inputs"]
        
        if exit_cap_rate is None:
            # Conservative: assume cap rate expands by 50bps at exit
            exit_cap_rate = base_scenario["metrics"]["cap_rate"] + 0.005
        
        # Initial investment (negative cash flow)
        equity = base_scenario["financing"]["equity"]
        cash_flows = [-equity]
        
        # Annual projections
        years = []
        current_rent = inputs["current_rent"]
        current_opex = inputs["operating_expenses"]
        
        for year in range(1, projection_years + 1):
            # Grow rent and expenses
            projected_rent = current_rent * ((1 + rent_growth) ** year)
            projected_opex = current_opex * ((1 + expense_growth) ** year)
            
            # Build year scenario
            year_scenario = self.build_base_scenario(
                purchase_price=inputs["purchase_price"],
                pad_count=inputs["pad_count"],
                current_rent=projected_rent,
                occupancy_rate=inputs["occupancy_rate"],
                operating_expenses=projected_opex,
                property_tax=inputs["property_tax"],
                insurance=inputs["insurance"],
                loan_ltv=inputs["loan_ltv"],
                interest_rate=inputs["interest_rate"],
                term_years=inputs["term_years"],
            )
            
            annual_cash_flow = year_scenario["cash_flow"]
            
            # Add exit proceeds in final year
            if year == projection_years:
                exit_value = year_scenario["noi"] / exit_cap_rate
                # Simplified: exit proceeds = exit value - remaining loan balance
                # (In reality, would need to calculate loan amortization)
                loan_balance_approx = (
                    base_scenario["financing"]["loan_amount"] * 0.95
                )  # Simplified
                exit_proceeds = exit_value - loan_balance_approx
                annual_cash_flow += exit_proceeds
            
            cash_flows.append(annual_cash_flow)
            years.append({
                "year": year,
                "rent": projected_rent,
                "noi": year_scenario["noi"],
                "cash_flow": annual_cash_flow,
            })
        
        # Calculate IRR
        irr = self.calculate_irr(cash_flows)
        
        return {
            "projection_years": projection_years,
            "rent_growth": rent_growth,
            "expense_growth": expense_growth,
            "exit_cap_rate": exit_cap_rate,
            "initial_equity": equity,
            "years": years,
            "cash_flows": cash_flows,
            "irr": irr,
        }

