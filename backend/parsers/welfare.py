# parsers/welfare.py – פרסר קובץ רווחה גולמי (תמר)
# לוגיקה מאומתת על 4 קבצים (רווחה1, רווחה3, רווחה4, רווחה5):
#   184xxx = govt   = sum(col_total בשורות תשלומי ממשלה לסעיף)
#   134xxx = source = col10(שורת סיכום) + col10(ילדי_חוץ) + col10(הפרש)
#   חו"ז   = source - govt  (חיובי → זכות, שלילי → חובה)
# בדיקות חובה: sum(184)=summary_mishrad, abs(sum(choz))=summary_choz

import io
import datetime
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, Any, Optional
from collections import defaultdict
import pandas as pd


class WelfareParserError(Exception):
    pass


WELFARE_INDEX: Dict[str, Dict] = {
    "120211": {"debit": "1849999783", "credit": "1342212930"},
    "120214": {"credit": "1342212930"},
    "120217": {"debit": "1842203840", "credit": "1342203930"},
    "120218": {"credit": "1342212930"},
    "242410": {"debit": "1844301840", "credit": "1344301930"},
    "242498": {"debit": "1844301840", "credit": "1344301930"},
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
    "722040": {"debit": "1845110840", "credit": "1345110930"},
    "722041": {"debit": "1845209840", "credit": "1345209930"},
    "722042": {"debit": "1845210840", "credit": "1345210930"},
    "723010": {"debit": "1845303840", "credit": "1345303930"},
    "723011": {"debit": "1845305840", "credit": "1345305930"},
    "723012": {"debit": "1845306840", "credit": "1345306930"},
    "723013": {"debit": "1845308840", "credit": "1345308930"},
    "723014": {"debit": "1845308840", "credit": "1345308930"},
    "723020": {"debit": "1845310840", "credit": "1345310930"},
    "723040": {"debit": "1845325840", "credit": "1345325930"},
    "723041": {"debit": "1845326840", "credit": "1345326930"},
    "723050": {"debit": "1845325840", "credit": "1345325930"},
    "723051": {"debit": "1845326840", "credit": "1345326930"},
    "723054": {"debit": "1845332840", "credit": "1345332930"},
    "723060": {"debit": "1845334840", "credit": "1345334930"},
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
    "1039100": {"debit": "1847301840", "credit": "1347301930"},
    "1039320": {"debit": "1847401840", "credit": "1347401930"},
    "1039440": {"debit": "1847501840", "credit": "1347501930"},
    "1039441": {"debit": "1847502840", "credit": "1347502930"},
    "1039448": {"debit": "1847508840", "credit": "1347508930"},
    "1039483": {"debit": "1847511840", "credit": "1347511930"},
    "1039730": {"debit": "1847601840", "credit": "1347601930"},
    "1039733": {"debit": "1847602840", "credit": "1347602930"},
    "1039750": {"debit": "1847604840", "credit": "1347604930"},
    "1039751": {"debit": "1847605840", "credit": "1347605930"},
    "1039770": {"debit": "1847607840", "credit": "1847607930"},
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
        index_source  = f"DB ({len(index_map)} entries)"
        print(f"[INDEX] SOURCE=DB  entries={len(index_map)}")
    else:
        welfare_index = WELFARE_INDEX
        index_source  = "STATIC"
        print(f"[INDEX] SOURCE=STATIC")

    try:
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None)
    except Exception as e:
        raise WelfareParserError(f"לא ניתן לקרוא את הקובץ: {e}")

    _validate_welfare_format(sheets)

    sheet_name = "דוח התחשבנות" if "דוח התחשבנות" in sheets else "גרסה להדפסה"
    df = sheets[sheet_name]

    # ── רשות ──────────────────────────────────────────────────────────
    municipality = ""
    for i in range(min(8, len(df))):
        for j in range(len(df.columns)):
            v = str(df.iloc[i, j])
            if any(x in v for x in ['מ. א', 'מועצה', 'עיריית', 'מ.א', 'מ.מ']):
                municipality = v.strip()
                break

    # ── תקופה ─────────────────────────────────────────────────────────
    # תקופה — סדר עדיפויות:
    # 1. שם חודש עברי מ'לחודש:'
    # 2. 'דיווח רשות: M/YYYY' (גובר על השם העברי)
    # 3. 'שנת תקציב:' לשנה בלבד
    # fallback: תשלום לחודש X/YYYY לא בשימוש
    MONTHS_HE = {
        'ינואר': 1, 'פברואר': 2, 'מרץ': 3, 'אפריל': 4,
        'מאי': 5, 'יוני': 6, 'יולי': 7, 'אוגוסט': 8,
        'ספטמבר': 9, 'אוקטובר': 10, 'נובמבר': 11, 'דצמבר': 12
    }
    period_label = ""
    period_month = month
    period_year  = None

    for i in range(min(8, len(df))):
        row_vals = [str(df.iloc[i, j]).strip() for j in range(len(df.columns))]
        row_text = ' '.join(row_vals)

        # 1. שם חודש עברי מ'לחודש:'
        if 'לחודש:' in row_text and period_month is None:
            for v in row_vals:
                if v in MONTHS_HE:
                    period_month = MONTHS_HE[v]
                    break

        # 2. 'דיווח רשות: M/YYYY' — גובר תמיד
        if 'דיווח רשות' in row_text:
            m2 = re.search(r'דיווח רשות[:\s]+(\d+)/(\d{4})', row_text)
            if m2:
                period_month = int(m2.group(1))
                period_year  = int(m2.group(2))

        # 3. שנה מ'שנת תקציב:'
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
    period_label = f"{period_month}/{period_year}"

    # ── headers ───────────────────────────────────────────────────────
    header_row_idx = None
    col_semel = col_name_idx = col_maslul = col10_idx = col_total_idx = None

    for i in range(min(15, len(df))):
        row_vals = [str(v).strip() for v in df.iloc[i].tolist()]
        if 'חיוב בחודש זה' in row_vals:
            header_row_idx = i
            col_semel     = next((j for j,v in enumerate(row_vals) if 'סמל הסעיף'       in v), None)
            col_name_idx  = next((j for j,v in enumerate(row_vals) if v == 'שם סעיף'),     None)
            col_maslul    = next((j for j,v in enumerate(row_vals) if 'מסלול תשלום'      in v), None)
            col10_idx     = next((j for j,v in enumerate(row_vals) if 'זיכוי/חיוב בחודש' in v), None)
            col_total_idx = next((j for j,v in enumerate(row_vals) if 'סה"כ הוצאה'       in v), None)
            print(f"[PARSER] header={i} col_semel={col_semel} col_maslul={col_maslul} col10={col10_idx} col_total={col_total_idx}")
            break

    if header_row_idx is None:
        raise WelfareParserError("לא נמצאה שורת כותרות בקובץ")
    if col_semel is None:
        raise WelfareParserError("עמודת 'סמל הסעיף' לא נמצאה")

    # ── סיכומים מהדוח ─────────────────────────────────────────────────
    summary_mishrad: Optional[float] = None
    summary_choz:    Optional[float] = None

    for i in range(len(df) - 1, header_row_idx, -1):
        row_text = ' '.join(str(v) for v in df.iloc[i].tolist())
        for val in df.iloc[i].tolist():
            if pd.isna(val): continue
            s = str(val).replace(',', '').strip()
            if not re.fullmatch(r'-?\d+(\.\d+)?', s):
                continue
            if "סה''כ תשלומי ממשלה:" in row_text and summary_mishrad is None:
                summary_mishrad = abs(float(s)); break
            if "סה''כ חיוב/זיכוי רשות:" in row_text and summary_choz is None:
                summary_choz = abs(float(s)); break

    print(f"[SUMMARY] mishrad={summary_mishrad} choz={summary_choz}")

    # ── לולאת נתונים ──────────────────────────────────────────────────
    EXCLUDE_MASLUL = ['המחאות', 'שטרם נפדו', 'מסר']

    semel_data: Dict[str, dict] = defaultdict(lambda: {
        'name': '', 'govt': Decimal('0'), 'source': Decimal('0')
    })

    for i in range(header_row_idx + 1, len(df)):
        row = df.iloc[i]
        raw_semel = str(row.iloc[col_semel]) if col_semel < len(row) else ''
        if not raw_semel or raw_semel == 'nan':
            continue
        semel = _extract_semel(raw_semel)
        if not semel:
            continue

        maslul = str(row.iloc[col_maslul]).strip() if col_maslul and col_maslul < len(row) else ''
        name   = str(row.iloc[col_name_idx]).strip() if col_name_idx and col_name_idx < len(row) else ''
        c10    = _to_decimal(row.iloc[col10_idx]     if col10_idx     and col10_idx     < len(row) else None)
        ctotal = _to_decimal(row.iloc[col_total_idx] if col_total_idx and col_total_idx < len(row) else None)

        if name and name != 'nan':
            semel_data[semel]['name'] = name

        if any(k in maslul for k in EXCLUDE_MASLUL):
            continue

        # govt: עמודה T — תשלומי ממשלה בלבד → 184xxx חיוב
        if 'תשלומי ממשלה' in maslul:
            semel_data[semel]['govt'] += ctotal

        # source: עמודה K — שורת סיכום (ללא מסלול) + ילדי חוץ + הפרשים → 134xxx זכות
        # K = הכנסה כוללת (ממשלה + רשות + התאמות)
        # choz = T_ממשלה - K = summary_choz (מאומת על 5 קבצים)
        if not maslul or maslul.strip() in ('', ' '):
            semel_data[semel]['source'] += c10
        elif 'ילדי חוץ' in maslul or 'הפרש' in maslul:
            semel_data[semel]['source'] += c10

    # ── בנה rows ──────────────────────────────────────────────────────
    rows_out = []
    for semel, data in semel_data.items():
        govt   = data['govt']
        source = data['source']
        choz   = source - govt

        if govt == Decimal('0') and source == Decimal('0'):
            continue

        idx = _lookup_index(semel, welfare_index, index_source)
        rows_out.append({
            "semel":         semel,
            "name":          data['name'] or semel,
            "debit_account": idx.get('debit',  ''),
            "credit_account":idx.get('credit', ''),
            "has_ממשלה":    govt != Decimal('0'),
            "govt_amount":   govt,
            "source_amount": source,
            "choz_amount":   choz,
            "in_index":      bool(idx),
        })

    # ── בדיקות חובה ───────────────────────────────────────────────────
    total_govt   = sum(r['govt_amount']   for r in rows_out)
    total_source = sum(r['source_amount'] for r in rows_out)
    total_choz   = sum(r['choz_amount']   for r in rows_out)
    missing_index = [r for r in rows_out if not r['in_index'] and r['govt_amount'] != Decimal('0')]

    sm = Decimal(str(summary_mishrad)) if summary_mishrad else Decimal('0')
    sc = Decimal(str(summary_choz))    if summary_choz    else Decimal('0')

    print(f"[RECONCILE] govt={float(total_govt):,.0f} vs mishrad={float(sm):,.0f} diff={float(total_govt-sm):,.0f}")
    print(f"[RECONCILE] choz={float(total_choz):,.0f} vs summary_choz={float(sc):,.0f} diff={float(abs(total_choz)-sc):,.0f}")

    balance_ok = (abs(total_govt - sm) <= Decimal('5') and abs(abs(total_choz) - sc) <= Decimal('5'))

    if missing_index:
        print(f"[INDEX] MISSING COUNT={len(missing_index)}")
        for r in missing_index:
            print(f"  MISSING semel={r['semel']} name={r['name']}")

    return {
        "municipality":    municipality,
        "period":          period_label,
        "month":           period_month,
        "year":            period_year,
        "rows":            rows_out,
        "total_rows":      len([r for r in rows_out if r['govt_amount'] != 0 or r['source_amount'] != 0]),
        "missing_index":   missing_index,
        "row_errors":      [],
        "total_debit":     float(total_govt),
        "total_credit":    float(total_source),
        "summary_mishrad": float(sm),
        "summary_choz":    float(sc),
        "balance_ok":      balance_ok,
        "_welfare_index":  welfare_index,
    }


def apply_welfare_splits(parsed: dict):
    """
    3 מעברים עצמאיים:
    מעבר 1: שורות 184xxx לפי govt_amount (תשלומי ממשלה בלבד)
    מעבר 2: שורות 134xxx לפי source_amount (col10 סיכום)
    מעבר 3: שורת חו"ז אחת שיורית = total_debit - total_credit
    אין תלות הדדית בין המעברים. אין חו"ז פר-סעיף.
    """
    welfare_index = parsed.get("_welfare_index", {})
    choz_account  = welfare_index.get("חוז", {}).get("credit", "")

    if not choz_account:
        print("[WELFARE] WARNING: no 'חוז' in index_map — choz line skipped")

    matched = []
    missing = []

    # --- מעבר 1: שורות הוצאה/184 (govt = תשלומי ממשלה בלבד) ---
    # credit_account = חשבון 184xxx (הוצאה), side=debit (ח/ז 1)
    for row in parsed["rows"]:
        govt = row["govt_amount"]
        if govt == Decimal('0'):
            continue
        if not row["in_index"]:
            missing.append({**row, "error": f"סעיף {row['semel']} לא נמצא ב-INDEX"})
        acct_184 = row.get("credit_account", "")  # 184 = credit in DB index
        acct_134 = row.get("debit_account",  "")  # 134 = debit in DB index
        if govt > Decimal('0'):
            matched.append({
                "semel": row["semel"] if row["in_index"] else "",
                "name": row["name"],
                "account": acct_184,
                "amount": float(govt),
                "side": "debit",
                "description": f"רווחה {row['semel']} {row['name']}",
            })
        elif govt < Decimal('0'):
            matched.append({
                "semel": row["semel"] if row["in_index"] else "",
                "name": row["name"],
                "account": acct_134,
                "amount": float(abs(govt)),
                "side": "credit",
                "description": f"רווחה {row['semel']} {row['name']}",
            })

    # --- מעבר 2: שורות הכנסה/134 (source = סיכום + ילדי חוץ + הפרשים) ---
    # debit_account = חשבון 134xxx (הכנסה), side=credit (ח/ז 2)
    for row in parsed["rows"]:
        source = row["source_amount"]
        if source == Decimal('0'):
            continue
        acct_184 = row.get("credit_account", "")
        acct_134 = row.get("debit_account",  "")
        if source > Decimal('0'):
            matched.append({
                "semel": row["semel"] if row["in_index"] else "",
                "name": row["name"],
                "account": acct_134,
                "amount": float(source),
                "side": "credit",
                "description": f"רווחה {row['semel']} {row['name']}",
            })
        elif source < Decimal('0'):
            matched.append({
                "semel": row["semel"] if row["in_index"] else "",
                "name": row["name"],
                "account": acct_184,
                "amount": float(abs(source)),
                "side": "debit",
                "description": f"רווחה {row['semel']} {row['name']}",
            })

    # --- מעבר 3: שורת חו"ז שיורית אחת ---
    # choz = total_debit - total_credit
    # חיובי → זכות (משרד חייב לרשות)
    # שלילי → חובה (רשות חייבת למשרד)
    # מאומת: abs(choz) = summary_choz על 5 קבצים
    if choz_account:
        total_d = sum(Decimal(str(r["amount"])) for r in matched if r["side"] == "debit")
        total_c = sum(Decimal(str(r["amount"])) for r in matched if r["side"] == "credit")
        choz = total_d - total_c
        if abs(choz) >= Decimal("1"):
            side = "credit" if choz > 0 else "debit"
            matched.append({
                "semel": "", "name": 'חו"ז משרד הרווחה',
                "account": choz_account, "amount": float(abs(choz)),
                "side": side,
                "description": 'חו"ז משרד הרווחה',
            })
            print(f"[BALANCE] choz={float(abs(choz)):,.0f} side={side}")
        else:
            print(f"[BALANCE] מאוזן ללא שורת חוז (פער={float(choz):.2f})")

    total_d = sum(Decimal(str(r["amount"])) for r in matched if r["side"] == "debit")
    total_c = sum(Decimal(str(r["amount"])) for r in matched if r["side"] == "credit")
    print(f"[BALANCE] debit={float(total_d):,.0f} credit={float(total_c):,.0f} diff={float(total_d-total_c):,.0f}")

    return matched, missing
