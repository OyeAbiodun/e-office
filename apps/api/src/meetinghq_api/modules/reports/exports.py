"""Stable, branded report exports."""

from collections.abc import Sequence
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from meetinghq_api.modules.finance.exports import csv_bytes, document
from meetinghq_api.modules.reports.schemas import ReportResponse


def _records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _record(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def report_csv(report: ReportResponse) -> bytes:
    snapshot = report.authoritative_snapshot
    rows: list[Sequence[object]] = []
    for task in _records(snapshot.get("tasks")):
        rows.append(
            [
                "Task",
                task.get("title"),
                task.get("status"),
                task.get("due_date"),
                task.get("project_id"),
            ]
        )
    for activity in _records(snapshot.get("activities")):
        rows.append(
            [
                "Daily activity",
                activity.get("summary"),
                "Recorded",
                activity.get("date"),
                activity.get("project_id"),
            ]
        )
    return csv_bytes(["Source", "Title / summary", "Status", "Date", "Project"], rows)


def report_pdf(report: ReportResponse, organization: str) -> bytes:
    snapshot = report.authoritative_snapshot
    summary = _record(snapshot.get("summary"))
    narrative = report.narrative
    return document(
        f"{report.subject_name} · {report.period_type.title()} Report",
        organization,
        f"{report.period_start} – {report.period_end} · "
        f"{report.status.replace('_', ' ').title()} · Version {report.version}",
        [
            (
                "Executive summary",
                ["Tasks", "Completed", "Overdue", "Activities", "Meetings", "Projects"],
                [
                    [
                        summary.get("tasks_total", 0),
                        summary.get("tasks_completed", 0),
                        summary.get("tasks_overdue", 0),
                        summary.get("activities", 0),
                        summary.get("meetings", 0),
                        summary.get("projects", 0),
                    ]
                ],
                [28, 28, 28, 28, 28, 28],
            ),
            (
                "Narrative",
                ["Section", "Details"],
                [
                    ["Accomplishments", narrative.get("accomplishments") or "—"],
                    ["Challenges / blockers", narrative.get("challenges") or "—"],
                    ["Next priorities", narrative.get("next_priorities") or "—"],
                    ["Notes", narrative.get("notes") or "—"],
                ],
                [45, 125],
            ),
            (
                "Task detail",
                ["Task", "Status", "Priority", "Due"],
                [
                    [
                        item.get("title"),
                        item.get("status"),
                        item.get("priority"),
                        item.get("due_date"),
                    ]
                    for item in _records(snapshot.get("tasks"))
                ],
                [85, 30, 25, 30],
            ),
        ],
    )


def report_xlsx(report: ReportResponse) -> bytes:
    """Create a small standards-compliant XLSX without a second export framework."""
    rows: list[list[object]] = [["Source", "Title / summary", "Status", "Date", "Project"]]
    snapshot = report.authoritative_snapshot
    for task in _records(snapshot.get("tasks")):
        rows.append(
            [
                "Task",
                task.get("title"),
                task.get("status"),
                task.get("due_date"),
                task.get("project_id"),
            ]
        )
    for activity in _records(snapshot.get("activities")):
        rows.append(
            [
                "Daily activity",
                activity.get("summary"),
                "Recorded",
                activity.get("date"),
                activity.get("project_id"),
            ]
        )
    sheet_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for column_number, value in enumerate(row, start=1):
            column = chr(64 + column_number)
            cells.append(
                f'<c r="{column}{row_number}" t="inlineStr"><is><t>'
                f"{escape(str(value or ''))}</t></is></c>"
            )
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    workbook = BytesIO()
    with ZipFile(workbook, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'  # noqa: E501
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'  # noqa: E501
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'  # noqa: E501
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'  # noqa: E501
            "</Relationships>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'  # noqa: E501
            "</Relationships>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>',
        )
    return workbook.getvalue()
