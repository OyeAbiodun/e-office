"""Deterministic statutory and proration calculation tests."""

from datetime import date
from decimal import Decimal

import pytest

from meetinghq_api.modules.payroll.calculations import (
    CalculationInput,
    calculate,
    paye_amount,
    proration_factor,
)
from meetinghq_api.shared.exceptions import ValidationError


def test_configurable_paye_pension_nhf_and_components_are_decimal_exact() -> None:
    output = calculate(
        CalculationInput(
            basic_salary=Decimal("100000"),
            recurring_items=[
                {
                    "component_id": None,
                    "code": "HOUSING",
                    "name": "Housing",
                    "component_kind": "earning",
                    "calculation_type": "fixed",
                    "amount": Decimal("20000"),
                    "percentage": Decimal("0"),
                    "taxable": True,
                    "pensionable": True,
                },
                {
                    "component_id": None,
                    "code": "COOP",
                    "name": "Cooperative",
                    "component_kind": "deduction",
                    "calculation_type": "percentage",
                    "amount": Decimal("0"),
                    "percentage": Decimal("1.5"),
                    "taxable": False,
                    "pensionable": False,
                },
            ],
            adjustments=[
                {"adjustment_type": "bonus", "amount": Decimal("10000"), "reason": "Goal"}
            ],
            loan_deduction=Decimal("5000"),
            factor=Decimal("1"),
            paye_rules={
                "annual_relief_fixed": "0",
                "annual_relief_rate": "0",
                "bands": [{"limit": None, "rate": "10"}],
            },
            pension_rules={"basis": "pensionable", "employee_rate": "8", "employer_rate": "10"},
            nhf_rules={"basis": "basic", "employee_rate": "2.5"},
            paye_participates=True,
            pension_participates=True,
            nhf_participates=True,
        )
    )
    assert output.gross_pay == Decimal("130000.00")
    assert output.paye == Decimal("13000.00")
    assert output.pension_employee == Decimal("9600.00")
    assert output.pension_employer == Decimal("12000.00")
    assert output.nhf == Decimal("2500.00")
    assert output.other_deductions == Decimal("1500.00")
    assert output.loan_deductions == Decimal("5000.00")
    assert output.net_pay == Decimal("98400.00")
    assert output.employer_cost == Decimal("142000.00")


def test_paye_bands_and_minimum_tax_are_configurable() -> None:
    amount, detail = paye_amount(
        Decimal("100000"),
        {
            "annual_relief_fixed": "200000",
            "annual_relief_rate": "20",
            "minimum_tax_rate": "1",
            "bands": [
                {"limit": "300000", "rate": "7"},
                {"limit": "300000", "rate": "11"},
                {"limit": None, "rate": "15"},
            ],
        },
    )
    assert amount == Decimal("6500.00")
    assert detail["annual_relief"] == "440000.00"
    assert len(detail["bands"]) == 3


def test_proration_uses_explicit_calendar_or_working_day_policy() -> None:
    calendar = proration_factor(
        date(2026, 9, 1),
        date(2026, 9, 30),
        date(2026, 9, 16),
        None,
        Decimal("0"),
        {"proration_method": "calendar_days"},
    )
    working = proration_factor(
        date(2026, 9, 1),
        date(2026, 9, 30),
        date(2026, 9, 1),
        None,
        Decimal("2"),
        {"proration_method": "working_days", "working_weekdays": [0, 1, 2, 3, 4]},
    )
    assert calendar == Decimal("0.500000")
    assert working == Decimal("0.909091")


def test_invalid_statutory_values_fail_safely() -> None:
    with pytest.raises(ValidationError, match="non-negative finite"):
        paye_amount(
            Decimal("1000"),
            {"bands": [{"limit": None, "rate": "NaN"}]},
        )


def test_bonus_overtime_arrears_and_deduction_are_explainable() -> None:
    result = calculate(
        CalculationInput(
            basic_salary=Decimal("100000"),
            recurring_items=[],
            adjustments=[
                {"adjustment_type": "bonus", "amount": "10000", "reason": "Bonus"},
                {"adjustment_type": "overtime", "amount": "5000", "reason": "Overtime"},
                {"adjustment_type": "arrears", "amount": "3000", "reason": "Arrears"},
                {"adjustment_type": "deduction", "amount": "2500", "reason": "Recovery"},
            ],
            loan_deduction=Decimal("0"),
            factor=Decimal("1"),
            paye_rules=None,
            pension_rules=None,
            nhf_rules=None,
            paye_participates=False,
            pension_participates=False,
            nhf_participates=False,
        )
    )
    assert result.variable_earnings == Decimal("18000.00")
    assert result.other_deductions == Decimal("2500.00")
    assert result.net_pay == Decimal("115500.00")
    assert {item["code"] for item in result.items} >= {
        "BONUS",
        "OVERTIME",
        "ARREARS",
        "DEDUCTION",
    }
