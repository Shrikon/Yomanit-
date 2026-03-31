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
    # ── חירום ──────────────────────────────────────────────────────
    "120211": {"debit": "1849999783", "credit": "1342212930"},
    "120214": {"credit": "1342212930"},
    "120217": {"debit": "1842203840", "credit": "1342203930"},
    "120218": {"credit": "1342212930"},
    # ── אזרחים ותיקים וניצולי שואה ─────────────────────────────────
    "242410": {"debit": "1844301840", "credit": "1344301930"},
    "243410": {"debit": "1844409750", "credit": "1344409930"},
    "243415": {"debit": "1844419840", "credit": "1344416930"},
    "243417": {"debit": "1844414840", "credit": "1344414930"},
    "243418": {"debit": "1844408840", "credit": "1344408930"},
    "243419": {"debit": "1844501840", "credit": "1344501930"},
    "243420": {"credit": "1344409930"},
    "243430": {"debit": "1844414840", "credit": "1344414930"},
    "243438": {"debit": "1844408840", "credit": "1344408930"},
    # ── כוח אדם ─────────────────────────────────────────────────
    "513410": {"credit": "1341000930"},
    "513411": {"credit": "1341201930"},
    "513412": {"credit": "1341201930"},
    "513420": {"debit": "1841001840", "credit": "1341000932"},
    "513421": {"credit": "1341004930"},
    "513423": {"credit": "1341004930"},
    "513440": {"credit": "1341003930"},
    "513441": {"credit": "1341001930"},
    # ── נכים ושיקום ─────────────────────────────────────────────
    "721010": {"debit": "1846501840", "credit": "1346501930"},
    "721011": {"debit": "1846502840", "credit": "1346502930"},
    "721012": {"debit": "1846100840", "credit": "1346100930"},
    "721020": {"debit": "1845108840", "credit": "1345108930"},
    "721030": {"debit": "1845103840", "credit": "1345103930"},
    "721040": {"debit": "1845110840", "credit": "1345110930"},
    "721041": {"debit": "1845105840", "credit": "1345105930"},
    "721050": {"credit": "1346503930"},
    "721060": {"debit": "1845101840", "credit": "1345101930"},
    "722010": {"debit": "1846710840", "credit": "1346710930"},
    "722011": {"debit": "1846702840", "credit": "1346702930"},
    "722014": {"debit": "1845104840", "credit": "1345104930"},
    "722020": {"debit": "1846701840", "credit": "1346701930"},
    "722021": {"credit": "1346703930"},
    "722022": {"debit": "1346703931", "credit": "1346703931"},
    "722023": {"debit": "1846708840", "credit": "1346708930"},
    "722030": {"credit": "1346602930"},
    "722040": {"debit": "1845203840", "credit": "1345203930"},
    "722041": {"debit": "1845201840", "credit": "1345201930"},
    "722042": {"debit": "1845400840", "credit": "1345400930"},
    "722060": {"debit": "1845304840", "credit": "1345302930"},
    "722061": {"debit": "1845202840", "credit": "1345202930"},
    "722210": {"debit": "1846306840", "credit": "1346306930"},
    "722212": {"debit": "1846712840", "credit": "1346712930"},
    "722214": {"credit": "1346803930"},
    "722221": {"credit": "1345400930"},
    "722710": {"debit": "1846304840", "credit": "1346304930"},
    "723010": {"debit": "1846501840", "credit": "1346501930"},
    "723011": {"debit": "1846502840", "credit": "1346502930"},
    "723012": {"debit": "1846100840", "credit": "1346100930"},
    "723013": {"debit": "1845110840", "credit": "1345110930"},
    "723014": {"debit": "1845105840", "credit": "1345105930"},
    "723020": {"debit": "1845108840", "credit": "1345108930"},
    "723040": {"debit": "1845110840", "credit": "1345110930"},
    "723041": {"debit": "1845105840", "credit": "1345105930"},
    "723050": {"debit": "1846710840", "credit": "1346710930"},
    "723051": {"debit": "1846702840", "credit": "1346702930"},
    "723054": {"debit": "1845104840", "credit": "1345104930"},
    "723056": {"debit": "1846800842", "credit": "1346800931"},
    "723060": {"debit": "1845304840", "credit": "1345302930"},
    "723210": {"debit": "1846306840", "credit": "1346306930"},
    "723212": {"debit": "1846712840", "credit": "1346712930"},
    "723214": {"credit": "1346803930"},
    "723215": {"debit": "1845300840", "credit": "1345300930"},
    "723217": {"debit": "1845111840", "credit": "1345111930"},
    "723220": {"debit": "1846601840", "credit": "1346601930"},
    "723221": {"debit": "1846707840", "credit": "1346707930"},
    "723223": {"debit": "1846807840", "credit": "1346807930"},
    "723224": {"debit": "1846807840", "credit": "1346807930"},
    "723225": {"debit": "1845109840", "credit": "1345109930"},
    "723670": {"credit": "1342400930"},
    "723671": {"debit": "1846713840", "credit": "1346713930"},
    "723820": {"debit": "1846304840", "credit": "1346304930"},
    # ── ילדים ומשפחות ──────────────────────────────────────────
    "1038100": {"debit": "1842211840", "credit": "1342211930"},
    "1038400": {"debit": "1843506843", "credit": "1343506930"},
    "1038405": {"credit": "1343509930"},
    "1038408": {"credit": "1342405930"},
    "1038410": {"debit": "1843801840", "credit": "1343801930"},
    "1038411": {"debit": "1849012840", "credit": "1349012930"},
    "1038413": {"debit": "1843503840", "credit": "1343503930"},
    "1038417": {"debit": "1843802840", "credit": "1343802930"},
    "1039010": {"debit": "1843902840", "credit": "1343902930"},
    "1039100": {"credit": "1348301930"},
    "1039320": {"credit": "1317600413"},
    "1039322": {"credit": "1348205930"},
    "1039370": {"credit": "1349001930"},
    "1039440": {"debit": "1843501840", "credit": "1343501930"},
    "1039441": {"credit": "1343504930"},
    "1039448": {"debit": "1842400840", "credit": "1342406930"},
    "1039482": {"credit": "1343510930"},
    "1039483": {"debit": "1843508840", "credit": "1343508930"},
    # ── אלימות ומשפחה ─────────────────────────────────────────
    "1039730": {"credit": "1342401930"},
    "1039733": {"debit": "1842402840", "credit": "1342402930"},
    "1039734": {"debit": "1842407840", "credit": "1342407930"},
    "1039750": {"credit": "1342208930"},
    "1039751": {"debit": "1842213841", "credit": "1342213930"},
    "1039770": {"debit": "1842203840", "credit": "1342203930"},
    "1039771": {"debit": "1849009840", "credit": "1349009930"},
    "1039790": {"debit": "1842410841", "credit": "1342410930"},
    "1039800": {"debit": "1842400840", "credit": "1342406930"},
    "1039810": {"debit": "1842411840", "credit": "1342411930"},
    "1039820": {"credit": "1344420930"},
    # ── חוץ ביתי ───────────────────────────────────────────────
    "1165180": {"debit": "1847303840", "credit": "1347303930"},
    "1165531": {"debit": "1842210840", "credit": "1342210930"},
    "1165532": {"debit": "1847110840", "credit": "1347110930"},
    "1165600": {"debit": "1847200840", "credit": "1347200930"},
    "1165610": {"debit": "1847200840", "credit": "1347200930"},
    # ── התמכרויות וצעירים ─────────────────────────────────────
    "1175060": {"debit": "1847307840", "credit": "1347305930"},
    "1175063": {"credit": "1342204930"},
    "1175320": {"debit": "1847106840", "credit": "1347106930"},
    "1175328": {"credit": "1342212930"},
    "1175330": {"debit": "1847113840", "credit": "1347113930"},
    "1175331": {"debit": "1847115841", "credit": "1347115930"},
    "1175332": {"debit": "1847114841", "credit": "1347114930"},
    "1175370": {"debit": "1847117840", "credit": "1347117930"},
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

    # מצא שורת headers + סיכומים
    header_row_idx = None
    col_semel = col_name = col_maslul = col_total = col_zikuy = None
    summary_mishrad = None   # סה"כ תשלומי ממשלה
    summary_choz    = None   # סה"כ חיוב/זיכוי רשות

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

    # ── קריאת שורות סיכום משורת הדוח ──────────────────────────────
    # חיפוש לפי טקסט — לא לפי מספר שורה קשיח
    KEYWORDS_MISHRAD = ['תשלומי ממשלה']
    KEYWORDS_CHOZ    = ['חיוב/זיכוי רשות', 'זיכוי רשות']

    def _find_summary_value(keywords):
        for i in range(len(df) - 1, header_row_idx, -1):
            row = df.iloc[i]
            row_text = ' '.join(str(v) for v in row.tolist())
            if any(k in row_text for k in keywords):
                for val in row.tolist():
                    if pd.isna(val): continue
                    s = str(val).replace(',', '').strip()
                    import re as _re
                    if _re.fullmatch(r'-?\d+(\.\d+)?', s):
                        return abs(float(s))
        return None

    summary_mishrad = _find_summary_value(KEYWORDS_MISHRAD)
    summary_choz    = _find_summary_value(KEYWORDS_CHOZ)

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

        # חובה – שורות תשלומי ממשלה (לא רשות, לא ילדי חוץ, לא המחאות/מסר)
        # כולל שליליות — הן חלק מהנטו התקציבי
        EXCLUDE_MASLUL = ['המחאות', 'שטרם נפדו', 'מסר']
        if (maslul and maslul.strip() != '' and
                'רשות' not in maslul and
                'ילדי חוץ' not in maslul and
                not any(k in maslul for k in EXCLUDE_MASLUL)):
            semel_data[semel]['has_ממשלה'] = True
            semel_data[semel]['debit_total'] += total  # נטו כולל שליליות

        # זכות – שורות ריקות (סיכום סעיף) + ילדי חוץ
        if (not maslul or maslul.strip() == '') and zikuy != 0:
            semel_data[semel]['zikuy'] += zikuy  # += כי יכולות להיות כמה שורות

        if 'ילדי חוץ' in maslul and zikuy != 0:
            semel_data[semel]['zikuy'] += zikuy  # ילדי חוץ נכנסים לזכות

    # קרא שורות סיכום (בסוף הדוח)
    import re as _re
    for i in range(len(df) - 1, max(header_row_idx, len(df) - 20), -1):
        row = df.iloc[i]
        vals = [str(v).strip() for v in row.tolist()]
        row_text = ' '.join(v for v in vals if v and v != 'nan')
        if 'תשלומי ממשלה' in row_text and "סה''כ" in row_text:
            try: summary_mishrad = abs(float(vals[10]))
            except: pass
        if 'חיוב/זיכוי רשות' in row_text and "סה''כ" in row_text:
            try: summary_choz = abs(float(vals[10]))
            except: pass

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
        "summary_mishrad": float(summary_mishrad) if summary_mishrad else float(total_debit),
        "summary_choz":    float(summary_choz)    if summary_choz    else None,
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

        # mishrad: שתי תנועות נפרדות, סימן קובע צד
        # mishrad חיובי → חובה | שלילי → זכות
        if debit_total != Decimal("0"):
            if debit_total > Decimal("0") and row["debit_account"]:
                matched.append({
                    "semel":       row["semel"],
                    "name":        row["name"],
                    "account":     row["debit_account"],
                    "amount":      float(debit_total),
                    "side":        "debit",
                    "description": f"רווחה {row['semel']} {row['name']}",
                })
            elif debit_total < Decimal("0") and row["credit_account"]:
                matched.append({
                    "semel":       row["semel"],
                    "name":        row["name"],
                    "account":     row["credit_account"],
                    "amount":      float(abs(debit_total)),
                    "side":        "credit",
                    "description": f"רווחה {row['semel']} {row['name']}",
                })

        # zikuy חיובי → זכות | שלילי → חובה
        if zikuy != Decimal("0"):
            if zikuy > Decimal("0") and row["credit_account"]:
                matched.append({
                    "semel":       row["semel"],
                    "name":        row["name"],
                    "account":     row["credit_account"],
                    "amount":      float(zikuy),
                    "side":        "credit",
                    "description": f"רווחה {row['semel']} {row['name']}",
                })
            elif zikuy < Decimal("0") and row["debit_account"]:
                matched.append({
                    "semel":       row["semel"],
                    "name":        row["name"],
                    "account":     row["debit_account"],
                    "amount":      float(abs(zikuy)),
                    "side":        "debit",
                    "description": f"רווחה {row['semel']} {row['name']}",
                })

    # שורת חו"ז — מהדוח בלבד, ללא איזון מלאכותי
    # כלל זהב: בדוחות רווחה אין שורת איזון
    summary_choz = parsed.get("summary_choz")
    if summary_choz and Decimal(str(summary_choz)) > Decimal("0"):
        matched.append({
            "semel":       "חוז",
            "name":        'חו"ז משרד הרווחה',
            "account":     "700000000",
            "amount":      float(Decimal(str(summary_choz))),
            "side":        "credit",
            "description": 'חו"ז משרד הרווחה',
        })

    # בדיקת תקינות בלבד — לא מתקנים
    summary_mishrad = parsed.get("summary_mishrad")
    if summary_mishrad and summary_choz:
        total_credit = sum(Decimal(str(r["amount"])) for r in matched if r["side"] == "credit")
        expected_credit = Decimal(str(summary_mishrad)) - Decimal(str(summary_choz))
        gap = abs(total_credit - Decimal(str(summary_mishrad)))
        if gap > Decimal("1"):
            print(f"[WELFARE] WARNING: credit gap = {gap} (total_credit={total_credit}, mishrad={summary_mishrad})")

    return matched, missing