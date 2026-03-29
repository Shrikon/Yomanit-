# parsers/welfare.py – פרסר קובץ רווחה גולמי (תמר)
# לוגיקה:
# חובה = רק שורות תשלומי ממשלה (סכום כל השורות לאותו סעיף) + יש debit ב-INDEX
# זכות = זיכוי/חיוב בחודש זה מהשורה הריקה + יש credit ב-INDEX

import io
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import List, Dict, Any, Tuple
import pandas as pd


class WelfareParserError(Exception):
    pass


# ── INDEX: סמל סעיף → קודי חשבון ──────────────────────────────────────────
# debit  = תקציב חובה (רק לסעיפים עם תשלומי ממשלה)
# credit = תקציב זכות
WELFARE_INDEX = {
    "120211": {"debit": "1842200840", "credit": "1342200931"},
    "120214": {"credit": "1348200930"},
    "120217": {"debit": "1842400840", "credit": "1342400930"},
    "120218": {"credit": "1341001930"},
    "242410": {"debit": "1844300840", "credit": "1344300930"},
    "243411": {"debit": "1844500840", "credit": "1344500930"},
    "243415": {"credit": "1344500930"},
    "243419": {"credit": "1344400930"},
    "243420": {"credit": "1344500930"},
    "513410": {"credit": "1341000930"},
    "513411": {"credit": "1341000931"},
    "513420": {"debit": "1841001840", "credit": "1341001930"},
    "513421": {"credit": "1341011930"},
    "513422": {"credit": "1341011930"},
    "513441": {"credit": "1341000932"},
    "721020": {"debit": "1845300840", "credit": "1345300930"},
    "722020": {"debit": "1846700840", "credit": "1346700930"},
    "722021": {"debit": "1846700841", "credit": "1346700931"},
    "722022": {"credit": "1346701930"},
    "723020": {"debit": "1845300840", "credit": "1345300930"},
    "723054": {"debit": "1845100841", "credit": "1345100930"},
    "723225": {"debit": "1845100840", "credit": "1345100931"},
    "723672": {"credit": "1346700932"},
    "1038410": {"debit": "1843800840", "credit": "1343800930"},
    "1038413": {"debit": "1843501840"},
    "1039440": {"debit": "1843500840", "credit": "1343500930"},
    "1039483": {"debit": "1848520840", "credit": "1348520930"},
    "1039730": {"debit": "1842400841", "credit": "1342400931"},
    "1039770": {"debit": "1842200840", "credit": "1342200930"},
    "1039790": {"debit": "1842200841", "credit": "1342200932"},
    "1175060": {"debit": "1847300840", "credit": "1347300930"},
    "1175320": {"debit": "1847100840", "credit": "1347100930"},
    "1175331": {"credit": "1343510930"},
}


def _extract_semel(raw: str) -> str:
    """7 ספרות אחרונות ללא אפסים מובילים: 230090243415 → 243415"""
    s = str(raw).replace('.0', '').strip()
    if len(s) >= 7:
        return s[-7:].lstrip('0') or s[-1]
    return s.lstrip('0') or s


def _to_decimal(val) -> Decimal:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return Decimal("0")
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _validate_welfare_format(sheets: dict) -> None:
    if "דוח התחשבנות" not in sheets and "גרסה להדפסה" not in sheets:
        raise WelfareParserError(
            "קובץ לא תקני – חסר sheet 'דוח התחשבנות'. "
            "יש להעלות קובץ דוח התחשבנות רווחה (תמר)"
        )


def parse_welfare(content: bytes, month: int = None, index_map: Dict[str, Dict] = None) -> Dict[str, Any]:
    welfare_index = index_map if index_map is not None else WELFARE_INDEX
    try:
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
    except Exception as e:
        raise WelfareParserError(f"לא ניתן לקרוא את הקובץ: {e}")

    _validate_welfare_format(sheets)

    sheet_name = "דוח התחשבנות" if "דוח התחשבנות" in sheets else "גרסה להדפסה"
    df = sheets[sheet_name]

    # שם רשות
    municipality = ""
    for i in range(min(8, len(df))):
        for j in range(len(df.columns)):
            v = str(df.iloc[i, j])
            if any(x in v for x in ['מ. א', 'מועצה', 'עיריית', 'מ.א', 'מ.מ']):
                municipality = v.strip()
                break

    # חודש ושנה
    period_label = ""
    period_month = month
    period_year  = None
    import re
    for i in range(min(8, len(df))):
        for j in range(len(df.columns)):
            v = str(df.iloc[i, j])
            m = re.search(r'תשלום לחודש\s*(\d+)/(\d{4})', v)
            if m:
                period_month = int(m.group(1))
                period_year  = int(m.group(2))
                period_label = f"{period_month}/{period_year}"
                break

    if period_month is None:
        period_month = 1
    if period_year is None:
        import datetime
        period_year = datetime.datetime.now().year

    # מצא שורת headers
    header_row_idx = None
    col_semel = col_name = col_maslul = col_total = col_zikuy = None

    for i in range(min(15, len(df))):
        row_vals = [str(v).strip() for v in df.iloc[i].tolist()]
        if 'חיוב בחודש זה' in row_vals:
            header_row_idx = i
            col_semel  = next((j for j, v in enumerate(row_vals) if 'סמל הסעיף' in v), None)
            col_name   = next((j for j, v in enumerate(row_vals) if v == 'שם סעיף'), None)
            col_maslul = next((j for j, v in enumerate(row_vals) if 'מסלול תשלום' in v), None)
            col_total  = next((j for j, v in enumerate(row_vals) if 'סה"כ הוצאה' in v), None)
            col_zikuy  = next((j for j, v in enumerate(row_vals) if 'זיכוי/חיוב בחודש' in v), None)
            break

    if header_row_idx is None:
        raise WelfareParserError("לא נמצאה שורת כותרות בקובץ")
    if col_semel is None:
        raise WelfareParserError("עמודת 'סמל הסעיף' לא נמצאה")

    # אסוף נתונים לפי סעיף
    # debit_total = סכום כל שורות תשלומי ממשלה
    # zikuy = מהשורה הריקה
    semel_data: Dict[str, dict] = {}

    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        raw_semel = str(row.iloc[col_semel]) if col_semel < len(row) else ''
        if not raw_semel or raw_semel == 'nan':
            continue

        semel  = _extract_semel(raw_semel)
        maslul = str(row.iloc[col_maslul]).strip() if col_maslul and col_maslul < len(row) else ''
        name   = str(row.iloc[col_name]).strip() if col_name and col_name < len(row) else ''
        total  = float(row.iloc[col_total]) if col_total and col_total < len(row) and str(row.iloc[col_total]) != 'nan' else 0
        zikuy  = float(row.iloc[col_zikuy]) if col_zikuy and col_zikuy < len(row) and str(row.iloc[col_zikuy]) != 'nan' else 0

        if semel not in semel_data:
            semel_data[semel] = {
                'name':        name or semel,
                'has_ממשלה':  False,
                'debit_total': 0,
                'zikuy':       0,
            }

        # חובה – כל שורות תשלומי ממשלה (מס"ר, מת"ס, מסר-המחאות וכו')
        # לוקחים col19 (סה"כ הוצאה) ומסכמים את כולן
        if maslul and maslul.strip() not in [' ', ''] and 'רשות' not in maslul and 'ילדי חוץ' not in maslul:
            semel_data[semel]['has_ממשלה'] = True
            semel_data[semel]['debit_total'] += total

        # זכות – מהשורה הריקה בלבד
        if (not maslul or maslul.strip() == '') and zikuy != 0:
            semel_data[semel]['zikuy'] = zikuy

    # בנה rows
    rows = []
    for semel, data in semel_data.items():
        idx = welfare_index.get(semel, {})
        rows.append({
            "semel":         semel,
            "name":          data['name'],
            "debit_account": idx.get('debit', ''),
            "credit_account":idx.get('credit', ''),
            "has_ממשלה":    data['has_ממשלה'],
            "debit_total":   _to_decimal(data['debit_total']),
            "zikuy_hodesh":  _to_decimal(data['zikuy']),
            "in_index":      bool(idx),
        })

    total_debit  = sum(r['debit_total']         for r in rows if r['debit_account'] and r['has_ממשלה'])
    total_credit = sum(abs(r['zikuy_hodesh'])    for r in rows if r['credit_account'] and r['zikuy_hodesh'] != 0)

    return {
        "municipality":  municipality,
        "period":        period_label,
        "month":         period_month,
        "year":          period_year,
        "rows":          rows,
        "total_rows":    len([r for r in rows if r['debit_total'] != 0 or r['zikuy_hodesh'] != 0]),
        "missing_index": [r for r in rows if not r['in_index'] and (r['debit_total'] > 0 or r['zikuy_hodesh'] != 0)],
        "row_errors":    [],
        "total_debit":   float(total_debit),
        "total_credit":  float(total_credit),
        "balance_ok":    True,
    }


def apply_welfare_splits(parsed: dict) -> Tuple[List[Dict], List[Dict]]:
    """
    לוגיקה:
    - חובה: רק אם יש תשלומי ממשלה AND debit_account ב-INDEX → סכום = debit_total
    - זכות: אם יש credit_account AND zikuy_hodesh != 0 → סכום = abs(zikuy_hodesh)
    """
    matched = []
    missing = []

    for row in parsed["rows"]:
        debit_total = row["debit_total"]
        zikuy       = row["zikuy_hodesh"]

        if debit_total == Decimal("0") and zikuy == Decimal("0"):
            continue

        if not row["in_index"]:
            missing.append({**row, "error": f"סעיף {row['semel']} לא נמצא ב-INDEX"})
            continue

        # שורת חובה
        if row["has_ממשלה"] and row["debit_account"] and debit_total > Decimal("0"):
            matched.append({
                "semel":       row["semel"],
                "name":        row["name"],
                "account":     row["debit_account"],
                "amount":      float(debit_total),
                "side":        "debit",
                "description": f"רווחה {row['semel']} {row['name']}",
            })

        # שורת זכות
        if row["credit_account"] and zikuy != Decimal("0"):
            matched.append({
                "semel":       row["semel"],
                "name":        row["name"],
                "account":     row["credit_account"],
                "amount":      float(abs(zikuy)),
                "side":        "credit",
                "description": f"רווחה {row['semel']} {row['name']}",
            })

    return matched, missing           "description": f"רווחה {row['semel']} {row['name']}",
            })

    return matched, missing
