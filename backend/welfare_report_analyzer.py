"""
welfare_report_analyzer.py – דוח PDF חודשי לגזבר מקובץ Excel רווחה (תמר)

Usage:
    python welfare_report_analyzer.py <path_to_excel> <output_pdf_path>

מבנה הקובץ (גיליון 'דוח התחשבנות'):
    שורה 4 עמודה 14: שם החודש | שורה 5 עמודה 14: שם הרשות
    שורה 2 עמודה 19: אחוז מימון מצטבר
    עמודה 24: שם סעיף | עמודה 22: מסלול תשלום
    עמודה 7: הקצבה שנתית | עמודה 6: הוצאה מצטברת
    עמודה 4: יתרת הקצבה | עמודה 2: חיוב בחודש זה
    סמל סעיף: נשלף מגיליון 'גרסה להדפסה' עמודה 13 (שורות כותרת סעיף)
    שורות סיכום: col 22 == ' ' (whitespace), שורות משנה: col 22 == 'תשלומי ממשלה' וכו'
"""

import re
import sys
import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional

import openpyxl
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Constants ─────────────────────────────────────────────────────────
FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
FONT_NAME = "Arial"

# Sheet 1 ('דוח התחשבנות') column indices (0-based)
COL_CHARGE = 2     # חיוב בחודש זה
COL_BALANCE = 4    # יתרת הקצבה כספית
COL_EXPENSE = 6    # הוצאות להתחשבנות מצטברת
COL_BUDGET = 7     # הקצבה שנתית בשקלים 100%
COL_MASLUL = 22    # מסלול תשלום (summary rows have ' ')
COL_NAME = 24      # שם סעיף


@dataclass
class SectionRow:
    name: str
    semel: str
    budget_annual: float
    expense_cumulative: float
    balance: float
    charge_month: float
    utilization_pct: float


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


def _cell(all_rows, row_idx: int, col_idx: int):
    """Get cell value by 0-based row/col index."""
    if row_idx < len(all_rows) and col_idx < len(all_rows[row_idx]):
        return all_rows[row_idx][col_idx].value
    return None


def _extract_semel_from_text(text: str) -> Optional[str]:
    """Extract 6-digit semel from section header like '230090242410 שם סעיף'."""
    m = re.search(r'(\d{6,})', text.strip())
    if m:
        digits = m.group(1)
        # Last 6 digits for long codes, full number for shorter
        return digits[-6:] if len(digits) >= 12 else digits
    return None


def _build_semel_map(wb: openpyxl.Workbook) -> Dict[str, str]:
    """Build name→semel map from sheet 'גרסה להדפסה' section headers."""
    semel_map: Dict[str, str] = {}
    if "גרסה להדפסה" not in wb.sheetnames:
        return semel_map

    ws = wb["גרסה להדפסה"]
    for row in ws.rows:
        # Section header rows: only col 13 has text, rest are empty/None
        if len(row) <= 13:
            continue
        val = row[13].value
        if not val or not isinstance(val, str):
            continue
        val = val.strip()
        # Section header pattern: digits followed by Hebrew text
        m = re.match(r'(\d+)\s+(.+)', val)
        if m:
            semel = _extract_semel_from_text(m.group(1))
            name = m.group(2).strip()
            if semel and name:
                semel_map[name] = semel

    return semel_map


def parse_excel(path: str) -> ReportData:
    """קרא קובץ Excel של דוח התחשבנות והחזר ReportData."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    # Build semel lookup from sheet 2
    semel_map = _build_semel_map(wb)

    # Open sheet 1
    if "דוח התחשבנות" in wb.sheetnames:
        ws = wb["דוח התחשבנות"]
    elif "גרסה להדפסה" in wb.sheetnames:
        ws = wb["גרסה להדפסה"]
    else:
        raise ValueError(f"גיליון לא נמצא. קיימים: {wb.sheetnames}")

    all_rows = list(ws.rows)

    # Metadata (0-indexed positions verified from actual file)
    municipality = _safe_str(_cell(all_rows, 5, 14))
    month = _safe_str(_cell(all_rows, 4, 14))
    funding_pct = _safe_str(_cell(all_rows, 2, 19))

    # Find header row containing 'חיוב בחודש זה'
    header_row_idx = None
    for i in range(min(15, len(all_rows))):
        for c in all_rows[i]:
            if c.value and "חיוב בחודש זה" in _safe_str(c.value):
                header_row_idx = i
                break
        if header_row_idx is not None:
            break

    if header_row_idx is None:
        header_row_idx = 8  # fallback

    # Parse data — take only summary rows (col 22 is whitespace or empty)
    seen_names: dict = {}  # name → SectionRow (deduplicate)
    for i in range(header_row_idx + 1, len(all_rows)):
        row = all_rows[i]
        if len(row) <= COL_NAME:
            continue

        name = _safe_str(row[COL_NAME].value)
        if not name:
            continue
        if 'סה"כ' in name or "סה''כ" in name:
            continue

        # Filter: only summary rows (col 22 is whitespace or empty)
        maslul = _safe_str(row[COL_MASLUL].value) if len(row) > COL_MASLUL else ""
        if maslul and maslul not in (" ", ""):
            continue

        budget = _safe_float(row[COL_BUDGET].value if len(row) > COL_BUDGET else None)
        expense = _safe_float(row[COL_EXPENSE].value if len(row) > COL_EXPENSE else None)
        balance = _safe_float(row[COL_BALANCE].value if len(row) > COL_BALANCE else None)
        charge = _safe_float(row[COL_CHARGE].value if len(row) > COL_CHARGE else None)

        if budget == 0 and expense == 0 and balance == 0:
            continue

        utilization = (expense / budget * 100) if budget != 0 else 0.0
        semel = semel_map.get(name, "")

        seen_names[name] = SectionRow(
            name=name,
            semel=semel,
            budget_annual=budget,
            expense_cumulative=expense,
            balance=balance,
            charge_month=charge,
            utilization_pct=round(utilization, 1),
        )

    wb.close()

    rows = list(seen_names.values())
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


# ── PDF Generation (Canvas-based for reliable Hebrew rendering) ───────

def _register_font():
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))


def _fmt_num(val: float) -> str:
    if val == int(val):
        return f"{int(val):,}"
    return f"{val:,.2f}"


def _bidi(text: str) -> str:
    """Apply BiDi algorithm to convert logical Hebrew to visual order for PDF."""
    return get_display(str(text))


# Colors
CLR_HEADER_BG = (0.17, 0.24, 0.31)   # #2c3e50
CLR_HEADING = (0.10, 0.32, 0.46)      # #1a5276
CLR_ALT_ROW = (0.92, 0.95, 0.97)      # #eaf2f8
CLR_GRID = (0.6, 0.6, 0.6)


class _PdfWriter:
    """Canvas-based PDF writer with RTL table support."""

    def __init__(self, path: str):
        self.c = canvas.Canvas(path, pagesize=A4)
        self.page_w, self.page_h = A4
        self.margin = 15 * mm
        self.y = self.page_h - self.margin
        self.content_w = self.page_w - 2 * self.margin

    def _check_space(self, needed: float):
        if self.y - needed < self.margin:
            self.c.showPage()
            self.y = self.page_h - self.margin

    def draw_title(self, text: str):
        self._check_space(25)
        self.c.setFont(FONT_NAME, 16)
        self.c.setFillColorRGB(0, 0, 0)
        self.c.drawCentredString(self.page_w / 2, self.y, _bidi(text))
        self.y -= 25

    def draw_heading(self, text: str):
        self._check_space(22)
        self.y -= 6
        self.c.setFont(FONT_NAME, 12)
        self.c.setFillColorRGB(*CLR_HEADING)
        self.c.drawRightString(self.page_w - self.margin, self.y, _bidi(text))
        self.c.setFillColorRGB(0, 0, 0)
        self.y -= 16

    def draw_text(self, text: str, size: int = 9):
        self._check_space(14)
        self.c.setFont(FONT_NAME, size)
        self.c.setFillColorRGB(0, 0, 0)
        self.c.drawRightString(self.page_w - self.margin, self.y, _bidi(text))
        self.y -= 14

    def draw_kv_table(self, rows: List[List[str]]):
        """Draw a simple 2-column key-value table (RTL)."""
        row_h = 18
        total_h = len(rows) * row_h
        self._check_space(total_h + 5)

        x_right = self.page_w - self.margin
        col1_w = 55 * mm  # label column (right)
        col2_w = self.content_w - col1_w  # value column (left)

        for i, (label, value) in enumerate(rows):
            row_y = self.y - (i * row_h)
            # Alternating background
            if i % 2 == 1:
                self.c.setFillColorRGB(*CLR_ALT_ROW)
                self.c.rect(self.margin, row_y - 4, self.content_w, row_h, fill=1, stroke=0)
            # Grid lines
            self.c.setStrokeColorRGB(*CLR_GRID)
            self.c.setLineWidth(0.3)
            self.c.line(self.margin, row_y - 4, x_right, row_y - 4)
            # Label (right-aligned, right column)
            self.c.setFillColorRGB(0, 0, 0)
            self.c.setFont(FONT_NAME, 10)
            self.c.drawRightString(x_right - 3, row_y + 2, _bidi(label))
            # Value (right-aligned in left column)
            self.c.drawRightString(x_right - col1_w - 3, row_y + 2, _bidi(value))

        self.y -= total_h + 8

    def draw_data_table(self, headers: List[str], rows: List[List[str]],
                        col_widths: List[float]):
        """Draw a data table with header row. Columns in RTL order."""
        row_h = 16
        header_h = 20
        # Reverse for RTL display
        headers = list(reversed(headers))
        rows = [list(reversed(r)) for r in rows]
        col_widths = list(reversed(col_widths))

        total_h = header_h + len(rows) * row_h
        self._check_space(min(total_h, 200))  # at least header + a few rows

        x_left = self.margin

        def _draw_row(cells, y, h, is_header=False, bg=None):
            # Background
            if is_header:
                self.c.setFillColorRGB(*CLR_HEADER_BG)
                self.c.rect(x_left, y - 4, self.content_w, h, fill=1, stroke=0)
            elif bg:
                self.c.setFillColorRGB(*bg)
                self.c.rect(x_left, y - 4, self.content_w, h, fill=1, stroke=0)

            # Cell text
            if is_header:
                self.c.setFillColorRGB(1, 1, 1)
                self.c.setFont(FONT_NAME, 9)
            else:
                self.c.setFillColorRGB(0, 0, 0)
                self.c.setFont(FONT_NAME, 8)

            x = x_left
            for j, cell_text in enumerate(cells):
                cw = col_widths[j] if j < len(col_widths) else 30 * mm
                display_text = _bidi(cell_text)
                # Center text in cell
                text_w = self.c.stringWidth(display_text, FONT_NAME,
                                            9 if is_header else 8)
                text_x = x + (cw - text_w) / 2
                self.c.drawString(text_x, y + 2, display_text)
                x += cw

            # Grid lines
            self.c.setStrokeColorRGB(*CLR_GRID)
            self.c.setLineWidth(0.5)
            self.c.line(x_left, y - 4, x_left + self.content_w, y - 4)
            # Vertical lines
            x = x_left
            for cw in col_widths:
                self.c.line(x, y - 4, x, y - 4 + h)
                x += cw
            self.c.line(x, y - 4, x, y - 4 + h)

        # Draw header
        _draw_row(headers, self.y, header_h, is_header=True)
        self.y -= header_h

        # Draw data rows
        for i, row in enumerate(rows):
            self._check_space(row_h + 5)
            bg = CLR_ALT_ROW if i % 2 == 1 else None
            _draw_row(row, self.y, row_h, bg=bg)
            self.y -= row_h

        # Bottom border
        self.c.line(x_left, self.y + row_h - 4, x_left + self.content_w,
                    self.y + row_h - 4)
        self.y -= 8

    def spacer(self, h: float = 8):
        self.y -= h

    def save(self):
        self.c.save()


def generate_pdf(report: ReportData, output_path: str) -> str:
    """Generate the PDF report. Returns the output path."""
    _register_font()
    pdf = _PdfWriter(output_path)
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    # ── Title ──
    pdf.draw_title(f"דוח תקצוב והתחשבנות — {report.municipality}")
    pdf.spacer(6)

    # ── Section 1: Executive Summary ──
    pdf.draw_heading("סיכום מנהלים")
    pdf.draw_kv_table([
        ["רשות", report.municipality],
        ["חודש דיווח", report.month],
        ["אחוז מימון מצטבר", report.funding_pct],
        ['סה"כ הקצבה שנתית', _fmt_num(report.total_budget)],
        ['סה"כ הוצאה מצטברת', _fmt_num(report.total_expense)],
        ["סעיפים פעילים", str(report.active_count)],
        ["תאריך הפקה", now],
    ])
    pdf.spacer(10)

    # ── Section 2: Underutilized (balance > 20% of annual) ──
    pdf.draw_heading("סעיפים עם תקציב לא מנוצל (יתרה > 20% מהקצבה)")

    underutilized = [
        r for r in report.rows
        if r.budget_annual > 0 and r.balance > r.budget_annual * 0.2
    ]
    underutilized.sort(key=lambda r: r.balance, reverse=True)

    if underutilized:
        headers = ["שם סעיף", "סמל", "הקצבה שנתית", "הוצאה מצטברת", "יתרה",
                   "% ניצול"]
        data = [
            [r.name, r.semel, _fmt_num(r.budget_annual),
             _fmt_num(r.expense_cumulative), _fmt_num(r.balance),
             f"{r.utilization_pct}%"]
            for r in underutilized
        ]
        col_widths = [55 * mm, 22 * mm, 28 * mm, 28 * mm, 25 * mm, 20 * mm]
        pdf.draw_data_table(headers, data, col_widths)
    else:
        pdf.draw_text(".אין סעיפים עם יתרה מעל 20%")

    pdf.spacer(10)

    # ── Section 3: Overbudget (expense > budget) ──
    pdf.draw_heading("סעיפים עם חריגה (הוצאה > הקצבה)")

    overbudget = [
        r for r in report.rows
        if r.budget_annual > 0 and r.expense_cumulative > r.budget_annual
    ]
    overbudget.sort(
        key=lambda r: r.expense_cumulative - r.budget_annual, reverse=True
    )

    if overbudget:
        headers = ["שם סעיף", "סמל", "הקצבה שנתית", "הוצאה מצטברת",
                   "סכום חריגה"]
        data = [
            [r.name, r.semel, _fmt_num(r.budget_annual),
             _fmt_num(r.expense_cumulative),
             _fmt_num(r.expense_cumulative - r.budget_annual)]
            for r in overbudget
        ]
        col_widths = [55 * mm, 22 * mm, 30 * mm, 30 * mm, 30 * mm]
        pdf.draw_data_table(headers, data, col_widths)
    else:
        pdf.draw_text(".אין סעיפים עם חריגה תקציבית")

    pdf.save()
    return output_path


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) != 3:
        print("Usage: python welfare_report_analyzer.py <excel_path> <output_pdf>")
        sys.exit(1)

    excel_path = sys.argv[1]
    output_pdf = sys.argv[2]

    report = parse_excel(excel_path)

    print(f"[ANALYZER] רשות: {report.municipality}")
    print(f"[ANALYZER] חודש: {report.month}")
    print(f"[ANALYZER] מימון מצטבר: {report.funding_pct}")
    print(f"[ANALYZER] סעיפים פעילים: {report.active_count}")
    print(f'[ANALYZER] סה"כ הקצבה: {_fmt_num(report.total_budget)}')
    print(f'[ANALYZER] סה"כ הוצאה: {_fmt_num(report.total_expense)}')

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
