"""
Underwriting Autopilot service.

This service ingests property, loan, and trailing-twelve-month (T12) financial
data, then produces a comprehensive underwriting package:

* Baseline metrics (EGI, NOI, DSCR, cap rate, debt yield, cash-on-cash)
* Standardised stress tests (downside, upside, interest-rate shock, capex hit)
* Ten-year cash flow projection with IRR and equity multiple
* Qualitative recommendation (GREEN / YELLOW / RED) with highlights & risks

The goal is to give analysts a "first draft" underwriting memo that still keeps
humans in control of offer decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional
from uuid import UUID

from numpy_financial import irr as np_irr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import Deal, Lead, Park
from app.schemas.underwriting import (
    UnderwritingAssumptions,
    UnderwritingDealSummary,
    UnderwritingLoanTerms,
    UnderwritingMetricSummary,
    UnderwritingProjectionSummary,
    UnderwritingProjectionYear,
    UnderwritingPropertyProfile,
    UnderwritingRecommendation,
    UnderwritingRunRequest,
    UnderwritingRunResponse,
    UnderwritingScenarioResult,
    UnderwritingVerdict,
)
from app.schemas.underwriting import T12Financials

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NormalizedInputs:
    """Normalized view of underwriting inputs with derived helpers."""

    deal_id: Optional[UUID]
    property_profile: UnderwritingPropertyProfile
    loan_terms: UnderwritingLoanTerms
    t12: T12Financials
    assumptions: UnderwritingAssumptions
    purchase_price: float
    loan_amount: float
    gross_potential_rent: float
    vacancy_loss: float
    other_income: float
    operating_expenses: float
    capital_reserves: float
    stabilized_occupancy: float
    stabilization_years: int
    rent_growth: float
    expense_growth: float
    exit_cap_rate: float
    exit_year: int

    @property
    def property_name(self) -> str:
        return self.property_profile.name

    @property
    def address(self) -> Optional[str]:
        return self.property_profile.address

    @property
    def units(self) -> int:
        return self.property_profile.units

    @property
    def occupancy_rate(self) -> float:
        return self.property_profile.occupancy_rate

    @property
    def average_rent(self) -> float:
        return self.property_profile.average_rent

    @property
    def interest_rate(self) -> float:
        return self.loan_terms.interest_rate

    @property
    def amortization_years(self) -> int:
        return self.loan_terms.amortization_years

    @property
    def term_years(self) -> int:
        return self.loan_terms.term_years

    @property
    def equity(self) -> float:
        return max(self.purchase_price - self.loan_amount, 0.0)

    @property
    def loan_to_value(self) -> float:
        if self.purchase_price <= 0:
            return 0.0
        return self.loan_amount / self.purchase_price

    @property
    def effective_gross_income(self) -> float:
        return self.gross_potential_rent - self.vacancy_loss + self.other_income

    @property
    def vacancy_rate(self) -> float:
        if self.gross_potential_rent <= 0:
            return 0.0
        return min(max(self.vacancy_loss / self.gross_potential_rent, 0.0), 1.0)

    @property
    def occupancy_implied(self) -> float:
        return max(0.0, min(1.0, 1.0 - self.vacancy_rate))

    @property
    def per_unit_rent(self) -> float:
        if self.units <= 0:
            return 0.0
        return self.gross_potential_rent / (self.units * 12)


class UnderwritingAutopilotService:
    """Service orchestrating underwriting automation."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db

    async def run(self, payload: UnderwritingRunRequest) -> UnderwritingRunResponse:
        """Execute the underwriting pipeline and return structured results."""
        logger.info(
            "underwriting_autopilot_started",
            extra={
                "deal_id": str(payload.deal_id) if payload.deal_id else None,
                "property": payload.property.name,
                "units": payload.property.units,
            },
        )

        deal_context = await self._fetch_deal_context(payload.deal_id)
        normalized = self._normalize_inputs(payload, deal_context)

        base_case = self._build_scenario(
            normalized,
            name="Base Case",
            description="Baseline underwriting using supplied T12 and loan terms.",
            assumptions={
                "rent_multiplier": 1.0,
                "vacancy_rate": normalized.vacancy_rate,
                "expense_multiplier": 1.0,
                "interest_rate": normalized.interest_rate,
            },
        )

        stress_tests = self._build_stress_tests(normalized)
        projection = self._build_projection(normalized)

        base_case = base_case.model_copy(
            update={
                "modeled_irr": projection.irr,
                "classification": self._verdict(
                    base_case.metrics,
                    irr=projection.irr,
                    require_irr=True,
                ),
            }
        )

        recommendation = self._build_recommendation(
            normalized,
            base_case.metrics,
            projection,
        )

        deal_summary = UnderwritingDealSummary(
            deal_id=normalized.deal_id,
            property_name=normalized.property_name,
            address=normalized.address,
            units=normalized.units,
            occupancy_rate=normalized.occupancy_rate,
            purchase_price=normalized.purchase_price,
            loan_amount=normalized.loan_amount,
            equity=normalized.equity,
            loan_to_value=normalized.loan_to_value,
        )

        response = UnderwritingRunResponse(
            deal_summary=deal_summary,
            base_case=base_case,
            stress_tests=stress_tests,
            projection=projection,
            recommendation=recommendation,
        )

        logger.info(
            "underwriting_autopilot_completed",
            extra={
                "deal_id": str(payload.deal_id) if payload.deal_id else None,
                "verdict": recommendation.verdict.value,
                "irr": projection.irr,
                "dscr": base_case.metrics.dscr,
            },
        )

        return response

    async def _fetch_deal_context(
        self, deal_id: Optional[UUID]
    ) -> Optional[Dict[str, Any]]:
        """Fetch deal context (deal + park) if a UUID is provided."""
        if not deal_id or not self.db:
            return None

        stmt = (
            select(Deal, Lead, Park)
            .join(Lead, Deal.lead_id == Lead.id)
            .join(Park, Lead.park_id == Park.id)
            .where(Deal.id == deal_id)
        )

        result = await self.db.execute(stmt)
        row = result.one_or_none()

        if not row:
            logger.info(
                "underwriting_deal_context_missing",
                extra={"deal_id": str(deal_id)},
            )
            return None

        deal, lead, park = row
        return {"deal": deal, "lead": lead, "park": park}

    def _normalize_inputs(
        self,
        payload: UnderwritingRunRequest,
        deal_context: Optional[Dict[str, Any]],
    ) -> NormalizedInputs:
        """Normalize inputs and stitch in contextual data when available."""
        property_profile = payload.property
        loan_terms = payload.loan
        t12 = payload.t12
        assumptions = payload.assumptions

        purchase_price = property_profile.purchase_price

        loan_amount = loan_terms.loan_amount
        if loan_amount is None:
            if loan_terms.loan_to_value is None:
                msg = "Either loan_amount or loan_to_value must be provided."
                raise ValueError(msg)
            loan_amount = purchase_price * loan_terms.loan_to_value

        if loan_amount <= 0 or loan_amount > purchase_price:
            msg = "Loan amount must be positive and not exceed purchase price."
            raise ValueError(msg)

        if property_profile.occupancy_rate <= 0 and t12.gross_potential_rent > 0:
            # Derive occupancy from T12 vacancy if not provided
            implied = max(
                0.0,
                1.0
                - (
                    (t12.vacancy_loss + t12.credit_loss + t12.concessions)
                    / max(t12.gross_potential_rent, 1e-9)
                ),
            )
            property_profile = property_profile.model_copy(
                update={"occupancy_rate": implied}
            )

        total_vacancy = t12.vacancy_loss + t12.credit_loss + t12.concessions
        egi = t12.gross_potential_rent - total_vacancy + t12.other_income
        operating_expenses = t12.total_operating_expenses(egi)

        if operating_expenses >= egi and egi > 0:
            logger.warning(
                "operating_expense_ratio_exceeds_egi",
                extra={
                    "property": property_profile.name,
                    "operating_expenses": operating_expenses,
                    "egi": egi,
                },
            )

        normalized = NormalizedInputs(
            deal_id=payload.deal_id,
            property_profile=property_profile,
            loan_terms=loan_terms,
            t12=t12,
            assumptions=assumptions,
            purchase_price=purchase_price,
            loan_amount=loan_amount,
            gross_potential_rent=t12.gross_potential_rent,
            vacancy_loss=total_vacancy,
            other_income=t12.other_income,
            operating_expenses=operating_expenses,
            capital_reserves=t12.capital_reserves,
            stabilized_occupancy=max(
                property_profile.occupancy_rate, assumptions.stabilized_occupancy
            ),
            stabilization_years=assumptions.stabilization_years,
            rent_growth=assumptions.rent_growth,
            expense_growth=assumptions.expense_growth,
            exit_cap_rate=assumptions.exit_cap_rate,
            exit_year=assumptions.exit_year,
        )

        if deal_context and not normalized.address:
            park = deal_context.get("park")
            if park and getattr(park, "address", None):
                normalized = replace(
                    normalized,
                    property_profile=normalized.property_profile.model_copy(
                        update={"address": park.address}
                    ),
                )

        if normalized.equity <= 0:
            msg = "Equity must be positive after accounting for loan proceeds."
            raise ValueError(msg)

        return normalized

    def _build_scenario(
        self,
        normalized: NormalizedInputs,
        name: str,
        description: str,
        assumptions: Dict[str, float],
        *,
        rent_multiplier: float = 1.0,
        occupancy: Optional[float] = None,
        expense_multiplier: float = 1.0,
        interest_rate: Optional[float] = None,
        additional_capex: float = 0.0,
    ) -> UnderwritingScenarioResult:
        """Generic scenario builder used by base case and stress tests."""
        gross_rent = normalized.gross_potential_rent * rent_multiplier

        if occupancy is None:
            vacancy_loss = normalized.vacancy_loss * rent_multiplier
            if gross_rent > 0:
                occupancy_rate = max(
                    0.0,
                    min(1.0, 1.0 - (vacancy_loss / gross_rent)),
                )
            else:
                occupancy_rate = normalized.occupancy_implied
        else:
            occupancy_rate = max(0.0, min(1.0, occupancy))
            vacancy_loss = gross_rent * (1 - occupancy_rate)

        other_income = normalized.other_income * rent_multiplier

        effective_gross_income = gross_rent - vacancy_loss + other_income
        operating_expenses = normalized.operating_expenses * expense_multiplier

        annual_debt_service = self._calculate_annual_debt_service(
            normalized.loan_amount,
            interest_rate or normalized.interest_rate,
            normalized.amortization_years,
        )

        noi = effective_gross_income - operating_expenses
        net_cash_flow = (
            noi - annual_debt_service - normalized.capital_reserves - additional_capex
        )

        metrics = UnderwritingMetricSummary(
            effective_gross_income=effective_gross_income,
            noi=noi,
            operating_expenses=operating_expenses,
            operating_expense_ratio=(
                operating_expenses / effective_gross_income
                if effective_gross_income
                else 0.0
            ),
            cap_rate=(
                noi / normalized.purchase_price if normalized.purchase_price else 0.0
            ),
            dscr=noi / annual_debt_service if annual_debt_service else 0.0,
            debt_yield=noi / normalized.loan_amount if normalized.loan_amount else 0.0,
            cash_on_cash=(
                net_cash_flow / normalized.equity if normalized.equity else 0.0
            ),
            annual_debt_service=annual_debt_service,
            loan_to_value=normalized.loan_to_value,
            equity=normalized.equity,
            net_cash_flow=net_cash_flow,
            breakeven_occupancy=self._breakeven_occupancy(
                gross_potential_rent=gross_rent,
                other_income=other_income,
                operating_expenses=operating_expenses,
                debt_service=annual_debt_service,
                capital_reserves=normalized.capital_reserves,
            ),
            occupancy=occupancy_rate,
        )

        classification = self._verdict(metrics, require_irr=False)

        return UnderwritingScenarioResult(
            name=name,
            description=description,
            assumptions=assumptions,
            metrics=metrics,
            classification=classification,
        )

    def _build_stress_tests(
        self, normalized: NormalizedInputs
    ) -> List[UnderwritingScenarioResult]:
        """Generate the standard underwriting stress scenarios."""
        assumptions = normalized.assumptions
        scenarios: List[UnderwritingScenarioResult] = []

        downside_occupancy = max(
            0.0, normalized.occupancy_rate - assumptions.downside_vacancy_delta
        )
        scenarios.append(
            self._build_scenario(
                normalized,
                name="Downside Case",
                description="Occupancy drops and expenses climb 15%.",
                assumptions={
                    "occupancy": downside_occupancy,
                    "expense_multiplier": 1 + assumptions.downside_expense_increase,
                },
                occupancy=downside_occupancy,
                expense_multiplier=1 + assumptions.downside_expense_increase,
            )
        )

        upside_occupancy = max(
            normalized.occupancy_rate, assumptions.stabilized_occupancy
        )
        scenarios.append(
            self._build_scenario(
                normalized,
                name="Upside Case",
                description="Occupancy stabilises at target and rents increase 3%.",
                assumptions={
                    "occupancy": upside_occupancy,
                    "rent_multiplier": 1 + assumptions.upside_rent_growth,
                },
                occupancy=upside_occupancy,
                rent_multiplier=1 + assumptions.upside_rent_growth,
            )
        )

        scenarios.append(
            self._build_scenario(
                normalized,
                name="Interest Rate Shock",
                description="Refinance or rate environment shifts +200 bps.",
                assumptions={
                    "interest_rate": normalized.interest_rate
                    + assumptions.interest_rate_shock,
                },
                interest_rate=normalized.interest_rate
                + assumptions.interest_rate_shock,
            )
        )

        scenarios.append(
            self._build_scenario(
                normalized,
                name="Major Capex Hit",
                description="Immediate $150k capital project executed in Year 1.",
                assumptions={"one_time_capex": assumptions.major_capex_amount},
                additional_capex=assumptions.major_capex_amount,
            )
        )

        return scenarios

    def _build_projection(
        self, normalized: NormalizedInputs
    ) -> UnderwritingProjectionSummary:
        """Construct the 10-year plan including cash flows and IRR."""
        initial_equity = normalized.equity
        cash_flows = [-initial_equity]
        years: List[UnderwritingProjectionYear] = []

        annual_debt_service = self._calculate_annual_debt_service(
            normalized.loan_amount,
            normalized.interest_rate,
            normalized.amortization_years,
        )

        exit_value = 0.0
        exit_proceeds = 0.0

        for year in range(1, normalized.exit_year + 1):
            occupancy = self._projected_occupancy(normalized, year)
            gross_rent = normalized.gross_potential_rent * (
                (1 + normalized.rent_growth) ** year
            )
            other_income = normalized.other_income * (
                (1 + normalized.rent_growth) ** year
            )
            vacancy_loss = gross_rent * (1 - occupancy)
            effective_gross_income = gross_rent - vacancy_loss + other_income
            operating_expenses = normalized.operating_expenses * (
                (1 + normalized.expense_growth) ** year
            )
            noi = effective_gross_income - operating_expenses

            net_cash_flow = noi - annual_debt_service - normalized.capital_reserves
            remaining_balance = self._remaining_balance(
                normalized.loan_amount,
                normalized.interest_rate,
                normalized.amortization_years,
                payments_made=min(year, normalized.term_years) * 12,
            )

            if year == normalized.exit_year:
                exit_value = (
                    noi / normalized.exit_cap_rate if normalized.exit_cap_rate else 0.0
                )
                exit_proceeds = max(exit_value - remaining_balance, 0.0)
                net_cash_flow += exit_proceeds

            cash_flows.append(net_cash_flow)

            years.append(
                UnderwritingProjectionYear(
                    year=year,
                    occupancy=occupancy,
                    gross_potential_rent=gross_rent,
                    other_income=other_income,
                    vacancy_loss=vacancy_loss,
                    effective_gross_income=effective_gross_income,
                    operating_expenses=operating_expenses,
                    noi=noi,
                    annual_debt_service=annual_debt_service,
                    capital_reserves=normalized.capital_reserves,
                    net_cash_flow=net_cash_flow,
                    ending_loan_balance=remaining_balance,
                )
            )

        irr_value: Optional[float]
        equity_multiple: Optional[float]
        try:
            irr_value = float(np_irr(cash_flows))
        except (ValueError, OverflowError):
            irr_value = None

        if initial_equity > 0:
            equity_multiple = sum(cf for cf in cash_flows[1:]) / initial_equity
        else:
            equity_multiple = None

        return UnderwritingProjectionSummary(
            years=years,
            irr=irr_value,
            equity_multiple=equity_multiple,
            cash_flows=cash_flows,
            exit_value=exit_value,
            exit_proceeds=exit_proceeds,
            sale_year=normalized.exit_year,
        )

    def _build_recommendation(
        self,
        normalized: NormalizedInputs,
        metrics: UnderwritingMetricSummary,
        projection: UnderwritingProjectionSummary,
    ) -> UnderwritingRecommendation:
        """Compose a user-facing recommendation summarising the verdict."""
        irr = projection.irr
        verdict = self._verdict(metrics, irr=irr, require_irr=True)

        highlights: List[str] = []
        risks: List[str] = []

        if metrics.cap_rate >= 0.07:
            highlights.append(f"Cap rate of {metrics.cap_rate:.1%} meets target.")

        if metrics.dscr >= 1.25:
            highlights.append(
                f"DSCR of {metrics.dscr:.2f} supports lender requirements."
            )

        if irr and irr >= 0.15:
            highlights.append(
                f"Projected IRR {irr:.1%} at year {projection.sale_year}."
            )

        if metrics.cash_on_cash < 0.06:
            risks.append(f"Cash-on-cash return is thin at {metrics.cash_on_cash:.1%}.")
        if metrics.dscr < 1.15:
            risks.append(f"DSCR falls below lender comfort at {metrics.dscr:.2f}.")
        if irr is not None and irr < 0.12:
            risks.append(f"IRR under 12% ({irr:.1%}), revisit growth assumptions.")
        if metrics.operating_expense_ratio > 0.45:
            risks.append(
                f"Operating expense ratio {metrics.operating_expense_ratio:.1%} may limit NOI growth."
            )

        if not highlights:
            highlights.append(
                "Stabilization path improves occupancy and NOI over hold."
            )

        rationale = (
            "Automated underwriting based on submitted T12, loan terms, and projection"
            " assumptions. Analyst review required before final bid."
        )

        return UnderwritingRecommendation(
            verdict=verdict,
            rationale=rationale,
            highlights=highlights,
            risks=risks,
            irr=irr,
            cash_on_cash=metrics.cash_on_cash,
            dscr=metrics.dscr,
            cap_rate=metrics.cap_rate,
        )

    @staticmethod
    def _calculate_annual_debt_service(
        loan_amount: float,
        interest_rate: float,
        amortization_years: int,
    ) -> float:
        """Calculate annual debt service for an amortising loan."""
        if loan_amount <= 0:
            return 0.0

        monthly_payment = UnderwritingAutopilotService._monthly_payment(
            loan_amount, interest_rate, amortization_years
        )
        return monthly_payment * 12

    @staticmethod
    def _monthly_payment(
        loan_amount: float,
        interest_rate: float,
        amortization_years: int,
    ) -> float:
        """Compute the standard amortising loan monthly payment."""
        if loan_amount <= 0 or amortization_years <= 0:
            return 0.0

        monthly_rate = interest_rate / 12
        num_payments = amortization_years * 12

        if monthly_rate == 0:
            return loan_amount / num_payments

        factor = (1 + monthly_rate) ** num_payments
        return loan_amount * (monthly_rate * factor) / (factor - 1)

    @staticmethod
    def _breakeven_occupancy(
        gross_potential_rent: float,
        other_income: float,
        operating_expenses: float,
        debt_service: float,
        capital_reserves: float,
    ) -> float:
        """Compute breakeven occupancy threshold."""
        denominator = gross_potential_rent + other_income
        if denominator <= 0:
            return 0.0

        numerator = operating_expenses + debt_service + capital_reserves
        breakeven = numerator / denominator
        return max(0.0, min(breakeven, 1.0))

    @staticmethod
    def _remaining_balance(
        loan_amount: float,
        interest_rate: float,
        amortization_years: int,
        payments_made: int,
    ) -> float:
        """Remaining loan balance after a number of monthly payments."""
        if loan_amount <= 0:
            return 0.0

        monthly_rate = interest_rate / 12
        total_payments = amortization_years * 12
        payments_made = min(payments_made, total_payments)

        if monthly_rate == 0:
            payment = loan_amount / total_payments
            balance = loan_amount - payment * payments_made
            return max(balance, 0.0)

        monthly_payment = UnderwritingAutopilotService._monthly_payment(
            loan_amount, interest_rate, amortization_years
        )
        factor = (1 + monthly_rate) ** payments_made
        balance = loan_amount * factor - monthly_payment * ((factor - 1) / monthly_rate)
        return max(balance, 0.0)

    @staticmethod
    def _projected_occupancy(normalized: NormalizedInputs, year: int) -> float:
        """Project occupancy ramp towards stabilized levels."""
        if normalized.occupancy_rate >= normalized.stabilized_occupancy:
            return normalized.occupancy_rate

        ramp_years = max(normalized.stabilization_years, 1)
        delta = normalized.stabilized_occupancy - normalized.occupancy_rate
        progress = min(year, ramp_years)
        occupancy = normalized.occupancy_rate + (delta * (progress / ramp_years))
        return max(0.0, min(occupancy, normalized.stabilized_occupancy))

    @staticmethod
    def _verdict(
        metrics: UnderwritingMetricSummary,
        *,
        irr: Optional[float] = None,
        require_irr: bool = False,
    ) -> UnderwritingVerdict:
        """Determine verdict bucket based on thresholds."""
        irr_green = (irr is None and not require_irr) or (
            irr is not None and irr >= 0.15
        )
        irr_yellow = (irr is None and not require_irr) or (
            irr is not None and irr >= 0.12
        )

        if metrics.dscr >= 1.25 and metrics.cash_on_cash >= 0.08 and irr_green:
            return UnderwritingVerdict.GREEN

        if metrics.dscr >= 1.15 and metrics.cash_on_cash >= 0.06 and irr_yellow:
            return UnderwritingVerdict.YELLOW

        return UnderwritingVerdict.RED
