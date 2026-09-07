"""Deterministic document layouts and spreadsheet-safe CSV projections."""

import csv
import io
from collections.abc import Sequence
from datetime import UTC, datetime
from html import escape

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.styles import getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from meetinghq_api.modules.finance.schemas import (
    FinanceTransactionResponse,
    StatementResponse,
    VoucherDetailResponse,
    VoucherResponse,
)


def csv_bytes(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        safe = []
        for value in row:
            text = "" if value is None else str(value)
            if isinstance(value, str) and text.lstrip().startswith(
                ("=", "+", "-", "@", "\t", "\r")
            ):
                text = "'" + text
            safe.append(text)
        writer.writerow(safe)
    return output.getvalue().encode("utf-8-sig")


def voucher_csv(rows: Sequence[VoucherResponse]) -> bytes:
    return csv_bytes(
        [
            "Voucher",
            "Requester",
            "Department",
            "Purpose",
            "Currency",
            "Requested",
            "Approved",
            "Disbursed",
            "Outstanding",
            "Status",
            "Submitted",
        ],
        [
            [
                r.voucher_number,
                r.requester_name,
                r.department_name,
                r.title,
                r.currency,
                r.requested_amount,
                r.approved_amount,
                r.disbursed_amount,
                r.outstanding_amount,
                r.status,
                r.submitted_at,
            ]
            for r in rows
        ],
    )


def transaction_csv(rows: Sequence[FinanceTransactionResponse]) -> bytes:
    return csv_bytes(
        [
            "Reference",
            "Account",
            "Date",
            "Type",
            "Direction",
            "Currency",
            "Amount",
            "Description",
            "Voucher",
            "Reconciled",
            "Reconciliation reference",
        ],
        [
            [
                r.reference,
                r.account_name,
                r.transaction_date,
                r.transaction_type,
                r.direction,
                r.currency,
                r.amount,
                r.description,
                r.voucher_number,
                r.reconciled,
                r.reconciliation_reference,
            ]
            for r in rows
        ],
    )


def statement_csv(statement: StatementResponse) -> bytes:
    rows: list[list[object]] = [
        [statement.from_date, "Opening balance", "", "", "", statement.opening_balance]
    ]
    rows.extend(
        [
            [
                t.transaction_date,
                t.reference,
                t.description,
                t.amount if t.direction == "credit" else "",
                t.amount if t.direction == "debit" else "",
                t.running_balance,
            ]
            for t in statement.transactions
        ]
    )
    rows.append(
        [
            statement.to_date,
            "Closing balance",
            "",
            statement.credits,
            statement.debits,
            statement.closing_balance,
        ]
    )
    return csv_bytes(
        [
            "Date",
            "Reference",
            "Description",
            "Credit",
            "Debit",
            f"Balance ({statement.account.currency})",
        ],
        rows,
    )


def document(
    title: str,
    organization: str,
    subtitle: str,
    sections: Sequence[tuple[str, Sequence[str], Sequence[Sequence[object]], Sequence[float]]],
) -> bytes:
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 13
    story = [
        Paragraph(escape(organization), styles["Title"]),
        Paragraph(escape(title), styles["Heading1"]),
        Paragraph(escape(subtitle), styles["BodyText"]),
        Spacer(1, 6 * mm),
    ]
    for heading, headers, rows, widths in sections:
        story.append(Paragraph(escape(heading), styles["Heading2"]))
        cells = [
            [Paragraph(escape(str(v if v is not None else "—")), styles["BodyText"]) for v in row]
            for row in [headers, *rows]
        ]
        table = Table(
            cells, colWidths=[width * mm for width in widths], repeatRows=1, hAlign="LEFT"
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9effa")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#dbe2ed")),
                ]
            )
        )
        story += [table, Spacer(1, 5 * mm)]
    story.append(
        Paragraph(
            f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M UTC} · MeetingHQ", styles["BodyText"]
        )
    )
    SimpleDocTemplate(
        output,
        title=title,
        author="MeetingHQ",
        pagesize=(210 * mm, 297 * mm),
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=17 * mm,
    ).build(story)
    return output.getvalue()


def voucher_pdf(detail: VoucherDetailResponse, organization: str) -> bytes:
    v = detail.voucher
    return document(
        v.voucher_number,
        organization,
        f"{v.title} · {v.status.replace('_', ' ').title()} · {v.currency}",
        [
            (
                "Request",
                ["Requester", "Department", "Purpose"],
                [[v.requester_name, v.department_name, v.description or v.title]],
                [48, 45, 83],
            ),
            (
                "Line items",
                ["Description", "Qty", "Price", "Tax", "Amount"],
                [
                    [line.description, line.quantity, line.unit_price, line.tax_amount, line.amount]
                    for line in detail.line_items
                ],
                [68, 18, 30, 28, 32],
            ),
            (
                "Totals",
                ["Requested", "Approved", "Disbursed", "Outstanding"],
                [[v.requested_amount, v.approved_amount, v.disbursed_amount, v.outstanding_amount]],
                [44, 44, 44, 44],
            ),
            (
                "Approval history",
                ["Reviewer", "Decision", "Amount", "Comment"],
                [
                    [r.get("actor_name"), r["decision"], r["approved_amount"], r["comment"]]
                    for r in detail.reviews
                ],
                [43, 29, 30, 74],
            ),
            (
                "Disbursements",
                ["Date", "Reference", "Method", "Amount"],
                [
                    [r["payment_date"], r["payment_reference"], r["payment_method"], r["amount"]]
                    for r in detail.disbursements
                ],
                [32, 76, 36, 32],
            ),
        ],
    )


def statement_pdf(statement: StatementResponse, organization: str) -> bytes:
    s = statement
    return document(
        "Account statement",
        organization,
        f"{s.account.account_name} ({s.account.account_code}) · {s.account.currency} · "
        f"{s.from_date} to {s.to_date}",
        [
            (
                "Period summary",
                ["Opening", "Credits", "Debits", "Closing"],
                [[s.opening_balance, s.credits, s.debits, s.closing_balance]],
                [44, 44, 44, 44],
            ),
            (
                "Transactions",
                ["Date / reference", "Description", "Credit", "Debit", "Balance"],
                [
                    [
                        f"{t.transaction_date} / {t.reference}",
                        t.description,
                        t.amount if t.direction == "credit" else "",
                        t.amount if t.direction == "debit" else "",
                        t.running_balance,
                    ]
                    for t in s.transactions
                ],
                [40, 58, 26, 26, 26],
            ),
        ],
    )
