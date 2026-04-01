# parsers/welfare.py – פרסר קובץ רווחה גולמי (תמר)
# זיהוי מבנה אוטומטי: new_structure (col_rasut+col_mishrad) או old_structure (col_total)
# חו"ז: חשבון מה-DB לפי key 'חוז', semel ריק

import io
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd


class WelfareParserError(Exception):
    pass


WELFARE_INDEX = {
    "120211": {"debit": "1849999783", "credit": "1342212930"},
    "120214": {"credit": "1342212930"},
    "120217": {"debit": "1842203840", "credit": "1342203930"},
    "120218": {"credit": "1342212930"},
    "242410": {"debit": "1844301840", "credit": "1344301930"},
    "243410": {"debit": "1844409750", "credit": "1344409930"},
    "243415": {"debit": "1844419840", "credit": "1344416930"},
    "243417": {"debit": "1844414840", "credit": "1344414930"},
    "243418": {"debit": "1844408840", "credit": "1344408930"},
    "243419": {"debit": "1844501840", "credit": "1344501930"},
    "243420": {"credit": "1344409930"},
    "243430": {"debit": "1844414840", "credit": "1344414930"},
    "243438": {"debit": "1844408840", "credit": "1344408930"},
    "513410": {"credit": "1341000930"},
    "513411": {"credit": "1341201930"},
    "513412": {"credit": "1341201930"},
    "513420": {"debit": "1841001840", "credit": "1341000932"},
    "513421": {"credit": "1341004930"},
    "513423": {"credit": "1341004930"},
    "513440": {"credit": "1341003930"},
    "513441": {"credit": "1341001930"},
    "721010": {"debit": "1846501840", "credit": "1346501930"},
    "721011": {"debit": "1846502840", "credit": "1346502930"},
    "721012": {"debit": "1846100840", "credit": "1346100930"},
    "721020": {"debit": "1845108840", "credit": "1345108930"},
    "721030": {"debit": "1845103840", "credit": "1345103930"},
    "721040": {"debit": "1845110840", "credit": "1345110930"},
    "721050": {"debit": "1845105840", "credit": "1345105930"},
    "721060": {"debit": "1845104840", "credit": "1345104930"},
    "722020": {"debit": "1845203840", "credit": "1345203930"},
    "722021": {"debit": "1845204840", "credit": "1345204930"},
    "722022": {"debit": "1845204840", "credit": "1345204930"},
    "722030": {"debit": "1845213840", "credit": "1345213930"},
    "722041": {"debit": "1845209840", "credit": "1345209930"},
    "722042": {"debit": "1845210840", "credit": "1345210930"},
    "723010": {"debit": "1845303840", "credit": "1345303930"},
    "723011": {"debit": "1845305840", "credit": "1345305930"},
    "723012": {"debit": "1845306840", "credit": "1345306930"},
    "723013": {"debit": "1845308840", "credit": "1345308930"},
    "723014": {"debit": "1845308840", "credit": "1345308930"},
    "723020": {"debit": "1845310840", "credit": "1345310930"},
    "723050": {"debit": "1845325840", "credit": "1345325930"},
    "723051": {"debit": "1845326840", "credit": "1345326930"},
    "723054": {"debit": "1845332840", "credit": "1345332930"},
    "723056": {"debit": "1845334840", "credit": "1845334930"},
    "723210": {"debit": "1845404840", "credit": "1345404930"},
    "723212": {"debit": "1845408840", "credit": "1345408930"},
    "723214": {"debit": "1845410840", "credit": "1345410930"},
    "723215": {"debit": "1845411840", "credit": "1345411930"},
    "723217": {"debit": "1845111840", "credit": "1345111930"},
    "723220": {"debit": "1845414840", "credit": "1345414930"},
    "723221": {"debit": "1845415840", "credit": "1345415930"},
    "723224": {"debit": "1845419840", "credit": "1345419930"},
    "723225": {"debit": "1845420840", "credit": "1345420930"},
    "723670": {"debit": "1845502840", "credit": "1345502930"},
    "723671": {"debit": "1845503840", "credit": "1345503930"},
    "723820": {"debit": "1845601840", "credit": "1345601930"},
    "1038100": {"debit": "1847101840", "credit": "1347101930"},
    "1038400": {"debit": "1847201840", "credit": "1347201930"},
    "1038405": {"debit": "1847202840", "credit": "1347202930"},
    "1038410": {"debit": "1847203840", "credit": "1347203930"},
    "1038411": {"debit": "1847204840", "credit": "1347204930"},
    "1038413": {"debit": "1847206840", "credit": "1347206930"},
    "1039010": {"debit": "1847301840", "credit": "1347301930"},
    "1039320": {"debit": "1847401840", "credit": "1347401930"},
    "1039440": {"debit": "1847501840", "credit": "1347501930"},
    "1039441": {"debit": "1847502840", "credit": "1347502930"},
    "1039448": {"debit": "1847508840", "credit": "1347508930"},
    "1039483": {"debit": "1847511840", "credit": "1347511930"},
    "1039730": {"debit": "1847601840", "credit": "1347601930"},
    "1039733": {"debit": "1847602840", "credit": "1347602930"},
    "1039750": {"debit": "1847604840", "credit": "1347604930"},
    "1039751": {"debit": "1847605840", "credit": "1347605930"},
    "1039770": {"debit": "1847607840", "credit": "1347607930"},
    "1039790": {"debit": "1847609840", "credit": "1347609930"},
    "1039810": {"debit": "1847611840", "credit": "1347611930"},
    "1165600": {"debit": "1848101840", "credit": "1348101930"},
    "1175060": {"debit": "1848201840", "credit": "1348201930"},
    "1175063": {"debit": "1848202840", "credit": "1348202930"},
    "1175320": {"debit": "1847106840", "credit": "1347106930"},
    "1175330": {"debit": "1848301840", "credit": "1348301930"},
    "1175331": {"debit": "1848302840", "credit": "1348302930"},
    "1175332": {"debit": "1848303840", "credit": "1348303930"},
    "1175370": {"debit": "1848401840", "credit": "1348401930"},
}

WELFARE_INCOME_ACCOUNT = "1340000000"


def _extract_semel(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    s = "".join(ch for ch in s if ch.isdigit())
    if not s:
        return None
    if len(s) >= 12:
        s = s[6:]
    return s


def _to_decimal(val) -> Decimal:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return Decimal("0")
        return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _validate_welfare_format(sheets: dict) -> None:
    if "דוח התחשבנות" not in sheets and "גרסה להדפסה" not in sheets:
        raise WelfareParserError(
            "קובץ לא תקני – חסר sheet 'דוח התחשבנות'. "
            "יש להעלות קובץ דוח התחשבנות רווחה (תמר)"
        )


def _lookup_index(semel: str, welfare_index: dict, index_source: str) -> dict:
    result = welfare_index.get(semel, {})
    if result:
        print(f"[LOOKUP] semel={semel} FOUND ({index_source}) debit={result.get('debit','—')} credit={result.get('credit','—')}")
    else:
        print(f"[LOOKUP] semel={semel} MISSING ({index_source})")
    return result


def parse_welfare(content: bytes, month: int = None, index_map: Dict[str, Dict] = None) -> Dict[str, Any]:
    if index_map is not None:
        welfare_index = index_map
        index_source = f"DB ({len(index_map)} entries)"
        print(f"[INDEX] SOURCE=DB  entries={len(index_map)}")
    else:
        welfare_index = WELFARE_INDEX
        index_source = "STATIC"
        print(f"[INDEX] SOURCE=STATIC (no index_map provided)")

    try:
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
    except Exception as e:
        raise WelfareParserError(f"לא ניתן לקרוא את הקובץ: {e}")

    _validate_welfare_format(sheets)

    sheet_name = "דוח התחשבנות" if "דוח התחשבנות" in sheets else "גרסה להדפסה"
    df = sheets[sheet_name]

    municipality = ""
    for i in range(min(8, len(df))):
        for j in range(len(df.columns)):
            v = str(df.iloc[i, j])
            if any(x in v for x in ['מ. א', 'מועצה', 'עיריית', 'מ.א', 'מ.מ']):
                municipality = v.strip()
                break

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

    header_row_idx = None
    col_semel = col_name = col_maslul = col_total = col_zikuy = None
    col_rasut = col_mishrad_col = None
    is_new_structure = False
    summary_mishrad = None
    summary_choz    = None

    for i in range(min(15, len(df))):
        row_vals = [str(v).strip() for v in df.iloc[i].tolist()]
        if 'חיוב בחודש זה' in row_vals:
            header_row_idx  = i
            col_semel       = next((j for j, v in enumerate(row_vals) if 'סמל הסעיף' in v), None)
            col_name        = next((j for j, v in enumerate(row_vals) if v == 'שם סעיף'), None)
            col_maslul      = next((j for j, v in enumerate(row_vals) if 'מסלול תשלום' in v), None)
            col_total       = next((j for j, v in enumerate(row_vals) if 'סה"כ הוצאה' in v), None)
            col_zikuy       = next((j for j, v in enumerate(row_vals) if 'זיכוי/חיוב בחודש' in v), None)
            col_rasut       = next((j for j, v in enumerate(row_vals) if 'חלק הרשות' in v), None)
            col_mishrad_col = next((j for j, v in enumerate(row_vals) if 'חלק המשרד לפי הסיווג' in v), None)
            is_new_structure = (col_rasut is not None and col_mishrad_col is not None)
            print(f"[PARSER] structure={'new (rasut+mishrad)' if is_new_structure else 'old (col_total)'}")
            break

    if header_row_idx is None:
        raise WelfareParserError("לא נמצאה שורת כותרות בקובץ")
    if col_semel is None:
        raise WelfareParserError("עמודת 'סמל הסעיף' לא נמצאה")

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

    semel_data: Dict[str, dict] = {}
    EXCLUDE_MASLUL = ['המחאות', 'שטרם נפדו', 'מסר']

    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        raw_semel = str(row.iloc[col_semel]) if col_semel < len(row) else ''
        if not raw_semel or raw_semel == 'nan':
            continue

        semel = _extract_semel(raw_semel)
        if not semel:
            continue

        maslul = str(row.iloc[col_maslul]).strip() if col_maslul and col_maslul < len(row) else ''
        name   = str(row.iloc[col_name]).strip()   if col_name   and col_name   < len(row) else ''
        total  = float(row.iloc[col_total])  if col_total  and col_total  < len(row) and str(row.iloc[col_total])  != 'nan' else 0
        zikuy  = float(row.iloc[col_zikuy])  if col_zikuy  and col_zikuy  < len(row) and str(row.iloc[col_zikuy])  != 'nan' else 0

        if semel not in semel_data:
            semel_data[semel] = {
                'name':          name or semel,
                'has_ממשלה':    False,
                'debit_total':   0,  # rasut + mishrad (כל ההוצאה)
                'mishrad_total': 0,  # mishrad בלבד (חלק המשרד)
                'zikuy':         0,
            }

        if 'תשלומי ממשלה' in maslul and not any(k in maslul for k in EXCLUDE_MASLUL):
            semel_data[semel]['has_ממשלה'] = True
            if col_rasut is not None and col_mishrad_col is not None:
                # חיוב = חלק רשות + חלק משרד (כל ההוצאה)
                v_rasut   = float(row.iloc[col_rasut])       if col_rasut       < len(row) and str(row.iloc[col_rasut])       != 'nan' else 0
                v_mishrad = float(row.iloc[col_mishrad_col]) if col_mishrad_col < len(row) and str(row.iloc[col_mishrad_col]) != 'nan' else 0
                semel_data[semel]['debit_total']  += v_rasut + v_mishrad
                semel_data[semel]['mishrad_total'] += v_mishrad
            else:
                semel_data[semel]['debit_total'] += total

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

    rows = []
    for semel, data in semel_data.items():
        idx = _lookup_index(semel, welfare_index, index_source)
        rows.append({
            "semel":         semel,
            "name":          data['name'],
            "debit_account": idx.get('debit', ''),
            "credit_account":idx.get('credit', ''),
            "has_ממשלה":    data['has_ממשלה'],
            "debit_total":   _to_decimal(data['debit_total']),   # rasut+mishrad → 184xxx
            "zikuy_hodesh":  _to_decimal(data['mishrad_total']), # mishrad בלבד → 134xxx
            "in_index":      bool(idx),
        })

    total_debit  = sum(r['debit_total'] for r in rows if r['debit_account'] and r['has_ממשלה'])
    total_credit = sum(r['debit_total'] for r in rows if r['credit_account'] and r['has_ממשלה'] and r['debit_total'] > 0)
    missing_index = [r for r in rows if not r['in_index'] and (r['debit_total'] > 0 or r['zikuy_hodesh'] != 0)]

    reconciliation: Dict[str, Any] = {}
    if summary_mishrad:
        sm  = Decimal(str(summary_mishrad))
        gap = sm - total_credit
        status = "balanced" if abs(gap) < Decimal("1") else "missing_index"
        reconciliation = {
            "summary_mishrad":      sm,
            "total_indexed_credit": total_credit,
            "gap":                  gap,
            "status":               status,
        }
        print(f"[RECONCILE] summary={sm} indexed_credit={total_credit} gap={gap} status={status}")
        if abs(gap) >= Decimal("1"):
            print(f"[RECONCILE] GAP={gap} — {len(missing_index)} missing index entries")

    if missing_index:
        print(f"[INDEX] MISSING COUNT={len(missing_index)}")
        for r in missing_index:
            print(f"  MISSING semel={r['semel']} name={r['name']}")

    return {
        "municipality":    municipality,
        "period":          period_label,
        "month":           period_month,
        "year":            period_year,
        "rows":            rows,
        "total_rows":      len([r for r in rows if r['debit_total'] != 0 or r['zikuy_hodesh'] != 0]),
        "missing_index":   missing_index,
        "row_errors":      [],
        "total_debit":     float(total_debit),
        "total_credit":    float(total_credit),
        "summary_mishrad": float(summary_mishrad) if summary_mishrad else float(total_debit),
        "summary_choz":    float(summary_choz)    if summary_choz    else None,
        "reconciliation":  reconciliation,
        "balance_ok":      reconciliation.get("status") == "balanced" if reconciliation else True,
        "_welfare_index":  welfare_index,
    }


def apply_welfare_splits(parsed: dict) -> tuple:
    matched = []
    missing = []

    for row in parsed["rows"]:
        debit_total = row["debit_total"]
        zikuy       = row["zikuy_hodesh"]

        if debit_total == Decimal("0") and zikuy == Decimal("0"):
            continue

        # דילוג על סעיפים ללא תשלומי ממשלה — לא שייכים לפקודה זו
        if not row["has_ממשלה"]:
            continue

        if not row["in_index"]:
            missing.append({**row, "error": f"סעיף {row['semel']} לא נמצא ב-INDEX"})
            continue

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

    # חו"ז — תמיד נלקח מ-summary_choz בדוח, תמיד בצד זכות
    # מייצג: יתרת התחשבנות מול המשרד (חוב של המשרד לרשות)
    # לא נגזר מחישוב — שקיפות מלאה מול הדוח
    welfare_index = parsed.get("_welfare_index", {})
    choz_account  = welfare_index.get("חוז", {}).get("credit", "")
    summary_choz  = parsed.get("summary_choz")

    if not choz_account:
        print(f"[WELFARE] WARNING: no 'חוז' entry in index_map — skipping choz line")
    elif summary_choz and Decimal(str(summary_choz)) > Decimal("0"):
        matched.append({
            "semel":       "",
            "name":        'חו"ז משרד הרווחה',
            "account":     choz_account,
            "amount":      float(Decimal(str(summary_choz))),
            "side":        "credit",
            "description": 'חו"ז משרד הרווחה',
        })
        print(f"[BALANCE] choz line: account={choz_account} amount={summary_choz} side=credit")

    return matched, missing
