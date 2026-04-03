#!/usr/bin/env python3
"""
דוח תקצוב והתחשבנות — דוח גזבר חודשי
========================================
מייצר PDF מקובץ Excel של משרד הרווחה (FI_2300).
שלושה חלקים: סיכום מנהלים, תקציב לא מנוצל, חריגות.

שימוש:
    python welfare_report_analyzer.py <excel_file> [month]
"""

import io
import sys
import re
import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, List, Optional, Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── פונטים ────────────────────────────────────────────────────────────
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

_font_registered = False

def _register_fonts():
    global _font_registered
    if _font_registered:
        return
    try:
        pdfmetrics.registerFont(TTFont("Hebrew", FONT_PATHS[0]))
        pdfmetrics.registerFont(TTFont("Hebrew-Bold", FONT_PATHS[1]))
    except Exception:
        pdfmetrics.registerFont(TTFont("Hebrew", FONT_PATHS[2]))
        pdfmetrics.registerFont(TTFont("Hebrew-Bold", FONT_PATHS[3]))
    _font_registered = True


# ── עזרים ─────────────────────────────────────────────────────────────

def _heb(text: str) -> str:
    """Reverse Hebrew text for RTL display in reportlab."""
    if not text:
        return ""
    try:
        from bidi.algorithm import get_display
        return get_display(text)
    except ImportError:
        return text[::-1] if any('\u0590' <= c <= '\u05FF' for c in text) else text


def _to_dec(val) -> Decimal:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return Decimal("0")
        return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _fmt_num(val, decimals=0) -> str:
    if val is None or val == 0:
        return "0"
    if decimals == 0:
        return f"{int(round(val)):,}"
    return f"{val:,.{decimals}f}"


def _pct(val) -> str:
    if val is None:
        return "—"
    return f"{val:.0f}%"


# ── פרסור Excel ──────────────────────────────────────────────────────

def parse_welfare_budget(content: bytes, month: int = None) -> Dict[str, Any]:
    """
    פרסור קובץ FI_2300 — חילוץ סעיפים עם הקצבה שנתית והוצאה מצטברת.
    """
    sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)

    sheet_name = None
    for name in ["דוח התחשבנות", "גרסה להדפסה"]:
        if name in sheets:
            sheet_name = name
            break
    if not sheet_name:
        raise ValueError("קובץ לא תקני – חסר sheet 'דוח התחשבנות'")

    df = sheets[sheet_name]

    # ── רשות ──
    municipality = ""
    for i in range(min(8, len(df))):
        for j in range(len(df.columns)):
            v = str(df.iloc[i, j])
            if any(x in v for x in ['מ. א', 'מועצה', 'עיריית', 'מ.א', 'מ.מ']):
                municipality = v.strip()
                break

    # ── תקופה ──
    MONTHS_HE = {
        'ינואר': 1, 'פברואר': 2, 'מרץ': 3, 'אפריל': 4,
        'מאי': 5, 'יוני': 6, 'יולי': 7, 'אוגוסט': 8,
        'ספטמבר': 9, 'אוקטובר': 10, 'נובמבר': 11, 'דצמבר': 12,
    }
    period_month = month
    period_year = None

    for i in range(min(8, len(df))):
        row_vals = [str(df.iloc[i, j]).strip() for j in range(len(df.columns))]
        row_text = ' '.join(row_vals)

        if 'לחודש:' in row_text and period_month is None:
            for v in row_vals:
                if v in MONTHS_HE:
                    period_month = MONTHS_HE[v]
                    break

        if 'דיווח רשות' in row_text:
            m2 = re.search(r'דיווח רשות[:\s]+(\d+)/(\d{4})', row_text)
            if m2:
                period_month = int(m2.group(1))
                period_year = int(m2.group(2))

        if 'שנת תקציב:' in row_text and period_year is None:
            for v in row_vals:
                m3 = re.search(r'(\d{4})', v)
                if m3:
                    period_year = int(m3.group(1))
                    break

    if period_month is None:
        period_month = 1
    if period_year is None:
        period_year = datetime.datetime.now().year

    # ── זיהוי עמודות ──
    header_row_idx = None
    col_semel = col_name = col_allocation = col_total_expense = None

    for i in range(min(15, len(df))):
        row_vals = [str(v).strip() for v in df.iloc[i].tolist()]
        if 'חיוב בחודש זה' in row_vals or any('סה"כ הוצאה' in v for v in row_vals):
            header_row_idx = i
            for j, v in enumerate(row_vals):
                if 'סמל הסעיף' in v or 'סמל סעיף' in v:
                    col_semel = j
                elif v == 'שם סעיף' or 'שם הסעיף' in v:
                    col_name = j
                elif any(kw in v for kw in ['הקצבה שנתית', 'הקצבה', 'תקציב מאושר', 'תקציב שנתי']):
                    col_allocation = j
                elif 'סה"כ הוצאה' in v or 'הוצאה מצטברת' in v:
                    col_total_expense = j
            break

    if header_row_idx is None:
        raise ValueError("לא נמצאה שורת כותרות בקובץ")
    if col_semel is None:
        raise ValueError("עמודת 'סמל הסעיף' לא נמצאה")

    # אם עמודת הקצבה לא נמצאה, חפש בשורת כותרות משנה
    if col_allocation is None:
        row_vals = [str(v).strip() for v in df.iloc[header_row_idx].tolist()]
        for j, v in enumerate(row_vals):
            if 'הקצבה' in v or 'תקציב' in v:
                col_allocation = j
                break

    # ── חילוץ נתונים ──
    EXCLUDE_MASLUL = ['המחאות', 'שטרם נפדו', 'מסר', 'תשלומי ממשלה']
    col_maslul = None
    row_vals = [str(v).strip() for v in df.iloc[header_row_idx].tolist()]
    for j, v in enumerate(row_vals):
        if 'מסלול תשלום' in v:
            col_maslul = j
            break

    sections: Dict[str, Dict] = {}

    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        raw_semel = str(row.iloc[col_semel]) if col_semel < len(row) else ''
        if not raw_semel or raw_semel == 'nan':
            continue

        # חילוץ סמל
        semel = raw_semel.strip()
        if semel.endswith(".0"):
            semel = semel[:-2]
        semel = "".join(ch for ch in semel if ch.isdigit())
        if not semel:
            continue
        if len(semel) >= 12:
            semel = semel[6:]

        # סנן מסלולים לא רלוונטיים
        maslul = ""
        if col_maslul and col_maslul < len(row):
            maslul = str(row.iloc[col_maslul]).strip()
        if any(k in maslul for k in EXCLUDE_MASLUL):
            continue
        # קח רק שורות סיכום (ללא מסלול) או שורות ראשיות
        if maslul and maslul not in ('', 'nan', ' '):
            continue

        name = ""
        if col_name and col_name < len(row):
            name = str(row.iloc[col_name]).strip()
            if name == 'nan':
                name = ""

        allocation = Decimal("0")
        if col_allocation and col_allocation < len(row):
            allocation = _to_dec(row.iloc[col_allocation])

        total_expense = Decimal("0")
        if col_total_expense and col_total_expense < len(row):
            total_expense = _to_dec(row.iloc[col_total_expense])

        if semel not in sections:
            sections[semel] = {
                "semel": semel,
                "name": name,
                "annual_allocation": allocation,
                "cumulative_expense": total_expense,
            }
        else:
            if name and not sections[semel]["name"]:
                sections[semel]["name"] = name
            if allocation != 0:
                sections[semel]["annual_allocation"] = allocation
            if total_expense != 0:
                sections[semel]["cumulative_expense"] = total_expense

    items = [v for v in sections.values() if v["annual_allocation"] != 0 or v["cumulative_expense"] != 0]

    return {
        "municipality": municipality,
        "month": period_month,
        "year": period_year,
        "period": f"{period_month}/{period_year}",
        "items": items,
        "total_sections": len(items),
    }


# ── חישובים ──────────────────────────────────────────────────────────

def analyze_budget(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """חישוב מדדים תקציביים לכל סעיף."""
    month = parsed["month"]
    items = parsed["items"]
    ratio = Decimal(str(month)) / Decimal("12")

    analyzed = []
    for item in items:
        annual = item["annual_allocation"]
        expense = item["cumulative_expense"]
        proportional = (annual * ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        diff = expense - proportional
        remaining = annual - expense
        pct_used = float(expense / annual * 100) if annual != 0 else 0

        analyzed.append({
            **item,
            "proportional_budget": proportional,
            "diff": diff,
            "remaining": remaining,
            "pct_used": pct_used,
        })

    total_annual = sum(i["annual_allocation"] for i in analyzed)
    total_expense = sum(i["cumulative_expense"] for i in analyzed)
    total_proportional = sum(i["proportional_budget"] for i in analyzed)
    total_diff = total_expense - total_proportional
    overall_pct = float(total_expense / total_annual * 100) if total_annual else 0

    # סעיפים עם תקציב לא מנוצל: יתרה > 20% מהקצבה
    # ממוין לפי ערך מוחלט של ההפרש — מהגדול לקטן
    underutilized = sorted(
        [i for i in analyzed if i["annual_allocation"] > 0 and i["remaining"] > i["annual_allocation"] * Decimal("0.2")],
        key=lambda x: abs(float(x["diff"])),
        reverse=True,
    )

    # סעיפים עם חריגה: הוצאה > הקצבה
    # ממוין לפי ערך מוחלט של ההפרש — מהגדול לקטן
    overbudget = sorted(
        [i for i in analyzed if i["annual_allocation"] > 0 and i["cumulative_expense"] > i["annual_allocation"]],
        key=lambda x: abs(float(x["diff"])),
        reverse=True,
    )

    return {
        **parsed,
        "analyzed": analyzed,
        "underutilized": underutilized,
        "overbudget": overbudget,
        "summary": {
            "total_annual": total_annual,
            "total_expense": total_expense,
            "total_proportional": total_proportional,
            "total_diff": total_diff,
            "overall_pct": overall_pct,
        },
    }


# ── יצירת PDF ────────────────────────────────────────────────────────

def generate_pdf(analysis: Dict[str, Any]) -> bytes:
    """יצירת PDF עם 3 חלקים: סיכום, לא מנוצל, חריגות."""
    _register_fonts()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    # סגנונות
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "Title_HE", parent=styles["Title"],
        fontName="Hebrew-Bold", fontSize=16, alignment=1,
        spaceAfter=4 * mm,
    )
    style_subtitle = ParagraphStyle(
        "Subtitle_HE", parent=styles["Normal"],
        fontName="Hebrew", fontSize=10, alignment=1,
        textColor=colors.HexColor("#555555"), spaceAfter=6 * mm,
    )
    style_section = ParagraphStyle(
        "Section_HE", parent=styles["Heading2"],
        fontName="Hebrew-Bold", fontSize=13, alignment=2,
        spaceBefore=6 * mm, spaceAfter=3 * mm,
        textColor=colors.HexColor("#1F4E79"),
    )
    style_note = ParagraphStyle(
        "Note_HE", parent=styles["Normal"],
        fontName="Hebrew", fontSize=8, alignment=2,
        textColor=colors.HexColor("#888888"),
    )

    elements = []
    muni = analysis["municipality"]
    period = analysis["period"]
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    summary = analysis["summary"]

    # ── כותרת ──
    elements.append(Paragraph(_heb("דוח תקצוב והתחשבנות — דוח גזבר חודשי"), style_title))
    elements.append(Paragraph(
        _heb(f"{muni}  |  תקופה: {period}  |  הופק: {now}"),
        style_subtitle,
    ))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1F4E79")))
    elements.append(Spacer(1, 4 * mm))

    # ── חלק 1: סיכום מנהלים ──
    elements.append(Paragraph(_heb("1. סיכום מנהלים"), style_section))

    HEADER_BG = colors.HexColor("#1F4E79")
    HEADER_FG = colors.white
    ALT_BG = colors.HexColor("#F2F7FB")
    TOTAL_BG = colors.HexColor("#E2EFDA")
    WARN_BG = colors.HexColor("#FFF2CC")

    summary_data = [
        [_heb("ערך"), _heb("מדד")],
        [_heb(muni), _heb("רשות")],
        [_heb(period), _heb("חודש דיווח")],
        [_pct(summary["overall_pct"]), _heb("% מימון מצטבר")],
        [_heb(f'₪{_fmt_num(float(summary["total_annual"]))}'), _heb('סה"כ הקצבה שנתית')],
        [_heb(f'₪{_fmt_num(float(summary["total_expense"]))}'), _heb('סה"כ הוצאה מצטברת')],
        [_heb(f'₪{_fmt_num(float(summary["total_proportional"]))}'), _heb("תקציב יחסי לתקופה")],
        [_heb(f'₪{_fmt_num(float(summary["total_diff"]))}'), _heb("הפרש כולל")],
    ]

    summary_table = Table(summary_data, colWidths=[120 * mm, 80 * mm])
    summary_style = TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Hebrew"),
        ("FONTNAME", (0, 0), (-1, 0), "Hebrew-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), HEADER_FG),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    # הפרש שלילי = בסדר (ירוק), חיובי = חריגה (אדום)
    diff_val = float(summary["total_diff"])
    diff_row = len(summary_data) - 1
    if diff_val > 0:
        summary_style.add("TEXTCOLOR", (0, diff_row), (0, diff_row), colors.HexColor("#C00000"))
    else:
        summary_style.add("TEXTCOLOR", (0, diff_row), (0, diff_row), colors.HexColor("#006100"))

    summary_table.setStyle(summary_style)
    elements.append(summary_table)
    elements.append(Spacer(1, 8 * mm))

    # ── חלק 2: סעיפים עם תקציב לא מנוצל ──
    elements.append(Paragraph(
        _heb(f"2. סעיפים עם תקציב לא מנוצל ({len(analysis['underutilized'])})"),
        style_section,
    ))
    elements.append(Paragraph(
        _heb("סעיפים שיתרתם עולה על 20% מההקצבה השנתית, ממוין מהיתרה הגבוהה לנמוכה"),
        style_note,
    ))
    elements.append(Spacer(1, 2 * mm))

    if analysis["underutilized"]:
        elements.append(_build_items_table(analysis["underutilized"], HEADER_BG, HEADER_FG, ALT_BG))
    else:
        elements.append(Paragraph(_heb("אין סעיפים עם תקציב לא מנוצל מעל 20%"), style_note))

    elements.append(Spacer(1, 8 * mm))

    # ── חלק 3: סעיפים עם חריגה ──
    elements.append(Paragraph(
        _heb(f"3. סעיפים עם חריגה ({len(analysis['overbudget'])})"),
        style_section,
    ))
    elements.append(Paragraph(
        _heb("סעיפים שההוצאה המצטברת עולה על ההקצבה השנתית, ממוין מהחריגה הגבוהה לנמוכה"),
        style_note,
    ))
    elements.append(Spacer(1, 2 * mm))

    if analysis["overbudget"]:
        elements.append(_build_items_table(analysis["overbudget"], HEADER_BG, HEADER_FG, WARN_BG))
    else:
        elements.append(Paragraph(_heb("אין סעיפים עם חריגה תקציבית — מצוין!"), style_note))

    doc.build(elements)
    return buf.getvalue()


def _build_items_table(items: List[Dict], header_bg, header_fg, alt_bg) -> Table:
    """בניית טבלת סעיפים."""
    headers = [
        _heb("% ניצול"),
        _heb("יתרה"),
        _heb("הפרש"),
        _heb("הוצאה מצטברת"),
        _heb("תקציב יחסי"),
        _heb("הקצבה שנתית"),
        _heb("סמל"),
        _heb("שם סעיף"),
    ]
    data = [headers]

    for item in items:
        row = [
            _pct(item["pct_used"]),
            _heb(f'₪{_fmt_num(float(item["remaining"]))}'),
            _heb(f'₪{_fmt_num(float(item["diff"]))}'),
            _heb(f'₪{_fmt_num(float(item["cumulative_expense"]))}'),
            _heb(f'₪{_fmt_num(float(item["proportional_budget"]))}'),
            _heb(f'₪{_fmt_num(float(item["annual_allocation"]))}'),
            item["semel"],
            _heb(item["name"] or item["semel"]),
        ]
        data.append(row)

    col_widths = [22 * mm, 30 * mm, 30 * mm, 35 * mm, 30 * mm, 35 * mm, 22 * mm, 55 * mm]

    table = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Hebrew"),
        ("FONTNAME", (0, 0), (-1, 0), "Hebrew-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), header_fg),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F8F8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])

    # צבע אדום להפרש חיובי (חריגה)
    for i in range(1, len(data)):
        diff_val = float(items[i - 1]["diff"])
        if diff_val > 0:
            style.add("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#C00000"))
        else:
            style.add("TEXTCOLOR", (2, i), (2, i), colors.HexColor("#006100"))

    table.setStyle(style)
    return table


# ── CLI ───────────────────────────────────────────────────────────────

def generate_from_file(filepath: str, month: int = None) -> bytes:
    """קריאת קובץ Excel ויצירת PDF."""
    with open(filepath, "rb") as f:
        content = f.read()
    parsed = parse_welfare_budget(content, month=month)
    analysis = analyze_budget(parsed)
    return generate_pdf(analysis)


def generate_from_bytes(content: bytes, month: int = None) -> bytes:
    """קבלת bytes של Excel ויצירת PDF."""
    parsed = parse_welfare_budget(content, month=month)
    analysis = analyze_budget(parsed)
    return generate_pdf(analysis)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("שימוש: python welfare_report_analyzer.py <excel_file> [month]")
        sys.exit(1)

    excel_path = sys.argv[1]
    month_arg = int(sys.argv[2]) if len(sys.argv) > 2 else None

    pdf_bytes = generate_from_file(excel_path, month=month_arg)

    out_name = excel_path.rsplit(".", 1)[0] + "_treasurer_report.pdf"
    with open(out_name, "wb") as f:
        f.write(pdf_bytes)
    print(f"דוח נוצר: {out_name} ({len(pdf_bytes):,} bytes)")
