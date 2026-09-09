"""Deterministic, configurable Payroll calculations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from meetinghq_api.shared.exceptions import ValidationError

ZERO = Decimal("0.00")
ONE = Decimal("1.000000")
CENT = Decimal("0.01")
RATE_UNIT = Decimal("100")
MONTHS = Decimal("12")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def decimal_rule(value: object, name: str, *, default: Decimal | None = None) -> Decimal:
    if value is None and default is not None:
        return default
    if isinstance(value, bool):
        raise ValidationError(f"{name} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValidationError(f"{name} must be numeric") from error
    if not result.is_finite() or result < 0:
        raise ValidationError(f"{name} must be a non-negative finite number")
    return result


def working_days(start: date, end: date, weekdays: set[int] | None = None) -> int:
    enabled = weekdays or {0, 1, 2, 3, 4}
    return sum(
        1
        for offset in range((end - start).days + 1)
        if (start + timedelta(days=offset)).weekday() in enabled
    )


def proration_factor(
    period_start: date,
    period_end: date,
    employment_start: date | None,
    employment_end: date | None,
    unpaid_leave_days: Decimal,
    policy: Mapping[str, object],
) -> Decimal:
    eligible_start = max(period_start, employment_start or period_start)
    eligible_end = min(period_end, employment_end or period_end)
    if eligible_start > eligible_end:
        return ZERO
    method = str(policy.get("proration_method", "calendar_days"))
    if method == "working_days":
        raw_weekdays = policy.get("working_weekdays", [0, 1, 2, 3, 4])
        if not isinstance(raw_weekdays, list):
            raise ValidationError("working_weekdays must be a list")
        weekdays = {int(day) for day in raw_weekdays}
        denominator = Decimal(working_days(period_start, period_end, weekdays))
        eligible = Decimal(working_days(eligible_start, eligible_end, weekdays))
    elif method == "calendar_days":
        denominator = Decimal((period_end - period_start).days + 1)
        eligible = Decimal((eligible_end - eligible_start).days + 1)
    else:
        raise ValidationError("proration_method must be calendar_days or working_days")
    if denominator <= 0:
        raise ValidationError("Payroll period contains no payable days")
    eligible = max(ZERO, eligible - unpaid_leave_days)
    return min(ONE, (eligible / denominator).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def paye_amount(
    taxable_monthly: Decimal, rules: Mapping[str, object]
) -> tuple[Decimal, dict[str, object]]:
    """Calculate PAYE using configured annual bands and reliefs."""
    annual_gross = money(taxable_monthly * MONTHS)
    relief_fixed = decimal_rule(
        rules.get("annual_relief_fixed"), "annual_relief_fixed", default=ZERO
    )
    relief_rate = decimal_rule(rules.get("annual_relief_rate"), "annual_relief_rate", default=ZERO)
    relief = money(relief_fixed + (annual_gross * relief_rate / RATE_UNIT))
    taxable_annual = max(ZERO, money(annual_gross - relief))
    raw_bands = rules.get("bands")
    if not isinstance(raw_bands, list) or not raw_bands:
        raise ValidationError("PAYE configuration requires at least one tax band")
    remaining = taxable_annual
    annual_tax = ZERO
    breakdown: list[dict[str, str]] = []
    for position, raw in enumerate(raw_bands):
        if not isinstance(raw, dict):
            raise ValidationError("Each PAYE band must be an object")
        rate = decimal_rule(raw.get("rate"), f"bands[{position}].rate")
        limit_raw = raw.get("limit")
        band_base = (
            remaining
            if limit_raw is None
            else min(remaining, decimal_rule(limit_raw, f"bands[{position}].limit"))
        )
        band_tax = money(band_base * rate / RATE_UNIT)
        annual_tax += band_tax
        breakdown.append({"base": str(money(band_base)), "rate": str(rate), "tax": str(band_tax)})
        remaining -= band_base
        if remaining <= 0:
            break
    if remaining > 0:
        raise ValidationError("PAYE bands do not cover taxable income")
    minimum_rate = decimal_rule(rules.get("minimum_tax_rate"), "minimum_tax_rate", default=ZERO)
    minimum_tax = money(annual_gross * minimum_rate / RATE_UNIT)
    annual_tax = max(money(annual_tax), minimum_tax)
    monthly = money(annual_tax / MONTHS)
    return monthly, {
        "method": "annualized_configurable_bands",
        "annual_gross": str(annual_gross),
        "annual_relief": str(relief),
        "taxable_annual": str(taxable_annual),
        "annual_tax": str(annual_tax),
        "monthly_tax": str(monthly),
        "bands": breakdown,
    }


def percentage_amount(basis: Decimal, rules: Mapping[str, object], key: str) -> Decimal:
    rate = decimal_rule(rules.get(key), key)
    return money(basis * rate / RATE_UNIT)


@dataclass(frozen=True, slots=True)
class CalculationInput:
    basic_salary: Decimal
    recurring_items: Sequence[Mapping[str, object]]
    adjustments: Sequence[Mapping[str, object]]
    loan_deduction: Decimal
    factor: Decimal
    paye_rules: Mapping[str, object] | None
    pension_rules: Mapping[str, object] | None
    nhf_rules: Mapping[str, object] | None
    paye_participates: bool
    pension_participates: bool
    nhf_participates: bool


@dataclass(frozen=True, slots=True)
class CalculationOutput:
    basic_salary: Decimal
    allowances: Decimal
    variable_earnings: Decimal
    gross_pay: Decimal
    taxable_pay: Decimal
    paye: Decimal
    pension_employee: Decimal
    pension_employer: Decimal
    nhf: Decimal
    loan_deductions: Decimal
    other_deductions: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    employer_cost: Decimal
    items: list[dict[str, object]]
    statutory_snapshot: dict[str, object]


def calculate(values: CalculationInput) -> CalculationOutput:
    factor = values.factor
    basic = money(values.basic_salary * factor)
    allowances = ZERO
    recurring_deductions = ZERO
    taxable = basic
    pensionable = basic
    items: list[dict[str, object]] = [
        {
            "code": "BASIC",
            "name": "Basic Salary",
            "category": "earning",
            "amount": basic,
            "taxable": True,
            "pensionable": True,
            "basis": f"{money(values.basic_salary)} × {factor}",
        }
    ]
    for item in values.recurring_items:
        calculation_type = str(item["calculation_type"])
        configured = decimal_rule(item.get("amount"), "component amount", default=ZERO)
        if calculation_type == "percentage":
            percentage = decimal_rule(item.get("percentage"), "component percentage")
            amount = money(values.basic_salary * percentage / RATE_UNIT * factor)
            basis = f"{percentage}% of basic × {factor}"
        else:
            amount = money(configured * factor)
            basis = f"{configured} × {factor}"
        kind = str(item["component_kind"])
        if kind == "earning":
            allowances += amount
            if bool(item.get("taxable")):
                taxable += amount
            if bool(item.get("pensionable")):
                pensionable += amount
        else:
            recurring_deductions += amount
        items.append(
            {
                "component_id": item.get("component_id"),
                "code": str(item["code"]),
                "name": str(item["name"]),
                "category": kind,
                "amount": amount,
                "taxable": bool(item.get("taxable")),
                "pensionable": bool(item.get("pensionable")),
                "basis": basis,
            }
        )
    variable_earnings = ZERO
    variable_deductions = ZERO
    for adjustment in values.adjustments:
        amount = money(decimal_rule(adjustment.get("amount"), "adjustment amount"))
        adjustment_type = str(adjustment["adjustment_type"])
        is_deduction = adjustment_type in {"deduction", "salary_advance"}
        if is_deduction:
            variable_deductions += amount
        else:
            variable_earnings += amount
            taxable += amount
        items.append(
            {
                "code": adjustment_type.upper(),
                "name": adjustment_type.replace("_", " ").title(),
                "category": "deduction" if is_deduction else "earning",
                "amount": amount,
                "taxable": not is_deduction,
                "pensionable": False,
                "basis": str(adjustment.get("reason") or "Period adjustment"),
            }
        )
    gross = money(basic + allowances + variable_earnings)
    taxable = money(taxable)
    statutory: dict[str, object] = {}
    paye = ZERO
    if values.paye_participates:
        if values.paye_rules is None:
            raise ValidationError("Missing effective PAYE configuration")
        paye, statutory["paye"] = paye_amount(taxable, values.paye_rules)
    pension_employee = pension_employer = ZERO
    if values.pension_participates:
        if values.pension_rules is None:
            raise ValidationError("Missing effective pension configuration")
        basis_name = str(values.pension_rules.get("basis", "pensionable"))
        pension_basis = pensionable if basis_name == "pensionable" else gross
        pension_employee = percentage_amount(pension_basis, values.pension_rules, "employee_rate")
        pension_employer = percentage_amount(pension_basis, values.pension_rules, "employer_rate")
        statutory["pension"] = {
            "basis": basis_name,
            "basis_amount": str(money(pension_basis)),
            "employee_rate": str(values.pension_rules.get("employee_rate")),
            "employer_rate": str(values.pension_rules.get("employer_rate")),
        }
    nhf = ZERO
    if values.nhf_participates:
        if values.nhf_rules is None:
            raise ValidationError("Missing effective NHF configuration")
        basis_name = str(values.nhf_rules.get("basis", "basic"))
        nhf_basis = basic if basis_name == "basic" else gross
        nhf = percentage_amount(nhf_basis, values.nhf_rules, "employee_rate")
        statutory["nhf"] = {
            "basis": basis_name,
            "basis_amount": str(money(nhf_basis)),
            "employee_rate": str(values.nhf_rules.get("employee_rate")),
        }
    loan = money(values.loan_deduction)
    other = money(recurring_deductions + variable_deductions)
    total = money(paye + pension_employee + nhf + loan + other)
    net = money(gross - total)
    employer_cost = money(gross + pension_employer)
    for code, name, amount, basis in (
        ("PAYE", "PAYE", paye, "Configured annualized PAYE rules"),
        ("PENSION_EMPLOYEE", "Employee Pension", pension_employee, "Configured pension basis"),
        ("NHF", "NHF", nhf, "Configured NHF basis"),
        ("LOAN", "Loan Repayment", loan, "Active scheduled repayments"),
    ):
        if amount:
            items.append(
                {
                    "code": code,
                    "name": name,
                    "category": "statutory" if code != "LOAN" else "deduction",
                    "amount": amount,
                    "taxable": False,
                    "pensionable": False,
                    "basis": basis,
                }
            )
    return CalculationOutput(
        basic,
        money(allowances),
        money(variable_earnings),
        gross,
        taxable,
        paye,
        pension_employee,
        pension_employer,
        nhf,
        loan,
        other,
        total,
        net,
        employer_cost,
        items,
        statutory,
    )
