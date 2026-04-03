"""
welfare_report_analyzer.py – דוח PDF חודשי לגזבר מקובץ Excel רווחה (תמר)

Usage:
    python welfare_report_analyzer.py <path_to_excel> <output_pdf_path>

מבנה הקובץ:
    גיליון: 'דוח התחשבנות' / 'גרסה להדפסה'
    עמודה 25: שם סעיף | עמודה 27: סמל סעיף
    עמודה 7: הקצבה שנתית | עמודה 6: הוצאה מצטברת
    עמודה 4: יתרת הקצבה | עמודה 2: חיוב בחודש זה
    שורה 5 עמודה 15: שם החודש | שורה 6 עמודה 15: שם הרשות
    שורה 3 עמודה 20: אחוז מימון מצטבר
"""

import sys
import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple

import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

# ── Constants ─────────────────────────────────────────────────────────
FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
FONT_NAME = "Arial"
SHEET_NAMES = ["דוח התחשבנות", "גרסה להדפסה"]

# Column indices (0-based)
COL_CHARGE_MONTH = 2   # חיוב בחודש זה
COL_BALANCE = 4        # יתרת הקצבה כספית
COL_EXPENSE_CUM = 6    # הוצאה מצטברת
COL_BUDGET_ANNUAL = 7  # הקצבה שנתית
COL_NAME = 25          # שם סעיף
COL_SEMEL = 27         # סמל סעיף

# Header metadata cell positions (row, col) — 0-based
POS_MONTH = (4, 15)        # שורה 5, עמודה 15
POS_MUNICIPALITY = (5, 15) # שורה 6, עמודה 15
POS_FUNDING_PCT = (2, 20)  # שורה 3, עמודה 20


@dataclass
class SectionRow:
    name: str
    semel: str
    budget_annual: float
    expense_cumulative: float
    balance: float
    charge_month: float
    utilization_pct: float  # אחוז ניצול


@dataclass
class ReportData:
    municipality: str
    month: str
    funding_pct: str
    total_budget: float
    total_expense: float
    active_count: int
    rows: List[SectionRow]


# ── Excel Reading ─────────────────────────────────────────────────────

def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _safe_str(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _find_sheet(wb: openpyxl.Workbook) -> openpyxl.worksheet.worksheet.Worksheet:
    for name in SHEET_NAMES:
        if name in wb.sheetnames:
            return wb[name]
    raise ValueError(
        f"גיליון לא נמצא. צפוי: {SHEET_NAMES}. קיימים: {wb.sheetnames}"
    )


def parse_excel(path: str) -> ReportData:
    """קרא קובץ Excel של דוח התחשבנות והחזר ReportData."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = _find_sheet(wb)

    # Read all rows into a list for indexed access
    all_rows = list(ws.rows)

    def cell(row_idx: int, col_idx: int):
        if row_idx < len(all_rows) and col_idx < len(all_rows[row_idx]):
            return all_rows[row_idx][col_idx].value
        return None

    # Header metadata
    municipality = _safe_str(cell(*POS_MUNICIPALITY))
    month = _safe_str(cell(*POS_MONTH))
    funding_pct = _safe_str(cell(*POS_FUNDING_PCT))

    # Find the header row (look for "חיוב בחודש זה" in first 15 rows)
    header_row_idx = None
    for i in range(min(15, len(all_rows))):
        for c in all_rows[i]:
            if c.value and "חיוב בחודש זה" in _safe_str(c.value):
                header_row_idx = i
                break
        if header_row_idx is not None:
            break

    if header_row_idx is None:
        # Fallback: assume data starts at row 8
        header_row_idx = 7

    # Parse data rows
    rows: List[SectionRow] = []
    for i in range(header_row_idx + 1, len(all_rows)):
        name = _safe_str(cell(i, COL_NAME))
        if not name or "סה\"כ" in name or 'סה"כ' in name or "סה''כ" in name:
            continue

        semel = _safe_str(cell(i, COL_SEMEL))
        budget = _safe_float(cell(i, COL_BUDGET_ANNUAL))
        expense = _safe_float(cell(i, COL_EXPENSE_CUM))
        balance = _safe_float(cell(i, COL_BALANCE))
        charge = _safe_float(cell(i, COL_CHARGE_MONTH))

        if budget == 0 and expense == 0 and balance == 0:
            continue

        utilization = (expense / budget * 100) if budget != 0 else 0.0

        rows.append(SectionRow(
            name=name,
            semel=semel,
            budget_annual=budget,
            expense_cumulative=expense,
            balance=balance,
            charge_month=charge,
            utilization_pct=round(utilization, 1),
        ))

    wb.close()

    total_budget = sum(r.budget_annual for r in rows)
    total_expense = sum(r.expense_cumulative for r in rows)

    return ReportData(
        municipality=municipality,
        month=month,
        funding_pct=funding_pct,
        total_budget=total_budget,
        total_expense=total_expense,
        active_count=len(rows),
        rows=rows,
    )


# ── PDF Generation ────────────────────────────────────────────────────

def _register_font():
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))


def _fmt_num(val: float) -> str:
    """Format number with thousands separator, no decimals for whole numbers."""
    if val == int(val):
        return f"{int(val):,}"
    return f"{val:,.2f}"


def _build_styles():
    title_style = ParagraphStyle(
        "Title", fontName=FONT_NAME, fontSize=16, alignment=TA_CENTER,
        leading=22, wordWrap="RTL",
    )
    heading_style = ParagraphStyle(
        "Heading", fontName=FONT_NAME, fontSize=12, alignment=TA_RIGHT,
        leading=16, wordWrap="RTL", textColor=colors.HexColor("#1a5276"),
    )
    body_style = ParagraphStyle(
        "Body", fontName=FONT_NAME, fontSize=9, alignment=TA_RIGHT,
        leading=12, wordWrap="RTL",
    )
    return title_style, heading_style, body_style


def _make_table(headers: List[str], data: List[List[str]], col_widths=None) -> Table:
    """Build an RTL table (headers + data rows reversed per row for RTL)."""
    # Reverse columns for RTL display
    reversed_headers = list(reversed(headers))
    reversed_data = [list(reversed(row)) for row in data]

    table_data = [reversed_headers] + reversed_data
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eaf2f8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def generate_pdf(report: ReportData, output_path: str) -> str:
    """Generate the PDF report. Returns the output path."""
    _register_font()
    title_style, heading_style, body_style = _build_styles()

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )

    elements = []
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    # ── Title ──
    elements.append(Paragraph(f"דוח תקצוב והתחשבנות — {report.municipality}", title_style))
    elements.append(Spacer(1, 4 * mm))

    # ── Section 1: Executive Summary ──
    elements.append(Paragraph("סיכום מנהלים", heading_style))
    elements.append(Spacer(1, 2 * mm))

    summary_data = [
        ["רשות", report.municipality],
        ["חודש דיווח", report.month],
        ["אחוז מימון מצטבר", report.funding_pct],
        ["סה\"כ הקצבה שנתית", _fmt_num(report.total_budget)],
        ["סה\"כ הוצאה מצטברת", _fmt_num(report.total_expense)],
        ["סעיפים פעילים", str(report.active_count)],
        ["תאריך הפקה", now],
    ]
    # Reverse for RTL
    summary_table = Table(
        [list(reversed(r)) for r in summary_data],
        colWidths=[120 * mm, 50 * mm],
    )
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 8 * mm))

    # ── Section 2: Underutilized Sections (balance > 20% of annual budget) ──
    elements.append(Paragraph("סעיפים עם תקציב לא מנוצל (יתרה > 20% מהקצבה)", heading_style))
    elements.append(Spacer(1, 2 * mm))

    underutilized = [
        r for r in report.rows
        if r.budget_annual > 0 and r.balance > r.budget_annual * 0.2
    ]
    underutilized.sort(key=lambda r: r.balance, reverse=True)

    if underutilized:
        headers = ["שם סעיף", "סמל", "הקצבה שנתית", "הוצאה מצטברת", "יתרה", "% ניצול"]
        data = [
            [
                r.name, r.semel,
                _fmt_num(r.budget_annual), _fmt_num(r.expense_cumulative),
                _fmt_num(r.balance), f"{r.utilization_pct}%",
            ]
            for r in underutilized
        ]
        col_widths = [55 * mm, 22 * mm, 28 * mm, 28 * mm, 25 * mm, 20 * mm]
        col_widths.reverse()
        elements.append(_make_table(headers, data, col_widths))
    else:
        elements.append(Paragraph("אין סעיפים עם יתרה מעל 20%.", body_style))

    elements.append(Spacer(1, 8 * mm))

    # ── Section 3: Overbudget Sections (expense > annual budget) ──
    elements.append(Paragraph("סעיפים עם חריגה (הוצאה > הקצבה)", heading_style))
    elements.append(Spacer(1, 2 * mm))

    overbudget = [
        r for r in report.rows
        if r.budget_annual > 0 and r.expense_cumulative > r.budget_annual
    ]
    overbudget.sort(
        key=lambda r: r.expense_cumulative - r.budget_annual, reverse=True
    )

    if overbudget:
        headers = ["שם סעיף", "סמל", "הקצבה שנתית", "הוצאה מצטברת", "סכום חריגה"]
        data = [
            [
                r.name, r.semel,
                _fmt_num(r.budget_annual), _fmt_num(r.expense_cumulative),
                _fmt_num(r.expense_cumulative - r.budget_annual),
            ]
            for r in overbudget
        ]
        col_widths = [55 * mm, 22 * mm, 30 * mm, 30 * mm, 30 * mm]
        col_widths.reverse()
        elements.append(_make_table(headers, data, col_widths))
    else:
        elements.append(Paragraph("אין סעיפים עם חריגה תקציבית.", body_style))

    doc.build(elements)
    return output_path


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 3:
        print("Usage: python welfare_report_analyzer.py <excel_path> <output_pdf>")
        sys.exit(1)

    excel_path = sys.argv[1]
    output_pdf = sys.argv[2]

    print(f"[ANALYZER] קורא קובץ: {excel_path}")
    report = parse_excel(excel_path)

    print(f"[ANALYZER] רשות: {report.municipality}")
    print(f"[ANALYZER] חודש: {report.month}")
    print(f"[ANALYZER] סעיפים פעילים: {report.active_count}")
    print(f"[ANALYZER] סה\"כ הקצבה: {_fmt_num(report.total_budget)}")
    print(f"[ANALYZER] סה\"כ הוצאה: {_fmt_num(report.total_expense)}")

    underutilized = [
        r for r in report.rows
        if r.budget_annual > 0 and r.balance > r.budget_annual * 0.2
    ]
    overbudget = [
        r for r in report.rows
        if r.budget_annual > 0 and r.expense_cumulative > r.budget_annual
    ]
    print(f"[ANALYZER] סעיפים לא מנוצלים: {len(underutilized)}")
    print(f"[ANALYZER] סעיפים בחריגה: {len(overbudget)}")

    generate_pdf(report, output_pdf)
    print(f"[ANALYZER] PDF נוצר: {output_pdf}")


if __name__ == "__main__":
    main()
