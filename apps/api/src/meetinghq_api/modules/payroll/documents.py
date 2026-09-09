"""Secure Payroll PDF and spreadsheet-safe export generation."""

from __future__ import annotations

from collections.abc import Sequence

from meetinghq_api.modules.finance.exports import csv_bytes, document
from meetinghq_api.modules.payroll.schemas import PayrollReportRow, PayrollResultResponse


def payslip_pdf(result: PayrollResultResponse, organization_name: str, period_name: str) -> bytes:
    earnings = [
        [item.name, item.basis or "—", item.amount]
        for item in result.items
        if item.category == "earning"
    ]
    deductions = [
        [item.name, item.basis or "—", item.amount]
        for item in result.items
        if item.category in {"deduction", "statutory"}
    ]
    return document(
        "Payslip",
        organization_name,
        f"{period_name} · {result.currency}",
        [
            (
                "Employee",
                ["Name", "Employee number", "Department", "Job title"],
                [
                    [
                        result.employee_name,
                        result.employee_number,
                        result.department_name,
                        result.job_title,
                    ]
                ],
                [48, 36, 46, 46],
            ),
            ("Earnings", ["Component", "Calculation", "Amount"], earnings, [50, 88, 38]),
            ("Deductions", ["Component", "Calculation", "Amount"], deductions, [50, 88, 38]),
            (
                "Summary",
                ["Gross pay", "Total deductions", "Net pay", "Employer cost"],
                [[result.gross_pay, result.total_deductions, result.net_pay, result.employer_cost]],
                [44, 44, 44, 44],
            ),
        ],
    )


def payroll_register_csv(rows: Sequence[PayrollResultResponse]) -> bytes:
    return csv_bytes(
        [
            "Employee number",
            "Employee",
            "Department",
            "Currency",
            "Basic",
            "Allowances",
            "Variable earnings",
            "Gross",
            "Taxable",
            "PAYE",
            "Employee pension",
            "Employer pension",
            "NHF",
            "Loan deductions",
            "Other deductions",
            "Total deductions",
            "Net",
            "Employer cost",
            "Status",
        ],
        [
            [
                row.employee_number,
                row.employee_name,
                row.department_name,
                row.currency,
                row.basic_salary,
                row.allowances,
                row.variable_earnings,
                row.gross_pay,
                row.taxable_pay,
                row.paye,
                row.pension_employee,
                row.pension_employer,
                row.nhf,
                row.loan_deductions,
                row.other_deductions,
                row.total_deductions,
                row.net_pay,
                row.employer_cost,
                row.status,
            ]
            for row in rows
        ],
    )


def statutory_summary_csv(rows: Sequence[PayrollReportRow]) -> bytes:
    return csv_bytes(
        [
            "Department",
            "Employees",
            "Gross",
            "PAYE",
            "Pension",
            "NHF",
            "Deductions",
            "Net",
            "Employer cost",
        ],
        [
            [
                row.group,
                row.employee_count,
                row.gross_pay,
                row.paye,
                row.pension,
                row.nhf,
                row.deductions,
                row.net_pay,
                row.employer_cost,
            ]
            for row in rows
        ],
    )
