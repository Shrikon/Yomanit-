# parsers/celcom.py – פרסר סלקום (3 קבצים)
#
# מבנה הקובץ:
#   rows 0-13:  כותרת (שם חברה, חשבונית, תאריך, סך לתשלום)
#   row 14:     כותרות עמודות (גיבוי — מחפשים "מספר לקוח")
#   rows 15+:   נתוני מנויים עד שורת סיכום
#
# עמודות מפתח:
#   col3  = מספר סלקום (טלפון)
#   col82 = סה"כ לפני מע"מ
#   col84 = חיובי מכשירים כולל מע"מ
#   col85 = סה"כ כולל מע"מ (הסכום לפקודה)
#
# הצלבה: sum(col85) == סך החשבונית לתשלום מהכותרת

import io
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any

import pandas as pd


class CelcomParserError(Exception):
    pass


VAT_RATE    = Decimal("1.18")
BALANCE_TOL = Decimal("0.10")

COL_PHONE       = 3
COL_NAME        = 4
COL_SNAME       = 5
COL_AC          = 28    # השתתפות חברה כולל מע"מ
COL_BEFORE_VAT  = 82    # סה"כ לפני מע"מ
COL_EXEMPT      = 83    # סה"כ פטור מע"מ
COL_DEVICES     = 84    # סה"כ חיובים/זיכויים כוללי מע"מ
COL_TOTAL       = 85    # סה"כ חשבונית כולל מע"מ


def normalize_phone(phone: Any) -> str:
    if phone is None:
        return ""
    phone = str(phone).strip()
    if phone.lower() in ("nan", "none", "", "0"):
        return ""
    phone = phone.replace("-", "").replace(" ", "")
    if "." in phone:
        phone = phone.split(".")[0]
    if phone.startswith("972"):
        phone = "0" + phone[3:]
    phone = phone.lstrip("0")
    if not phone.isdigit():
        return ""
    return phone.strip()


def _to_dec(val: Any) -> Decimal:
    if val is None:
        return Decimal("0")
    try:
        s = str(val).replace(",", "").strip()
        if not s or s.lower() in ("none", "nan"):
            return Decimal("0")
        if s.endswith(".0"):
            s = s[:-2]
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def _r2(d) -> Decimal:
    if not isinstance(d, Decimal):
        d = Decimal(str(d))
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_header(df: pd.DataFrame) -> dict:
    """Parse header rows 0-14 for invoice metadata and totals."""
    h11 = h12 = h13 = h14 = h_total = None
    inv_date = inv_num = customer_name = ""
    col_header_row = None

    for i in range(0, min(25, len(df))):
        label = str(df.iloc[i, 6] if len(df.columns) > 6 else "").strip()
        val   = df.iloc[i, 7] if len(df.columns) > 7 else None

        if "לפני מע" in label and "סך" in label and "תשלומים" not in label:
            h11 = _to_dec(val)
        elif "מע''מ" in label and "סך" in label and "לפני" not in label and "פטור" not in label:
            h12 = _to_dec(val)
        elif "פטור" in label and "סך" in label:
            h13 = _to_dec(val)
        elif "תשלומים עבור מכשיר" in label:
            h14 = _to_dec(val)
        elif "לתשלום" in label and "סך" in label:
            h_total = _to_dec(val)
        elif "תאריך החשבונית" in label:
            inv_date = str(val or "").strip()
        elif "מספר החשבונית" in label:
            inv_num = str(int(val) if val and str(val) != "nan" else "").strip()
        elif "שם חברה" in label:
            customer_name = str(val or "").strip()

        if col_header_row is None:
            for j in range(min(10, len(df.columns))):
                cell = str(df.iloc[i, j] or "").strip()
                if cell in ("מספר לקוח", "מספר סלקום"):
                    col_header_row = i
                    break

    if h11 is None or h12 is None:
        raise CelcomParserError("לא נמצאו סה\"כ לפני מע\"מ / סך מע\"מ בכותרת")
    if h_total is None:
        raise CelcomParserError("לא נמצא סך החשבונית לתשלום בכותרת")
    if col_header_row is None:
        col_header_row = 15

    h13 = h13 or Decimal("0")
    h14 = h14 or Decimal("0")

    return {
        "inv_date": inv_date, "inv_num": inv_num, "customer_name": customer_name,
        "H11": _r2(h11), "H12": _r2(h12), "H13": _r2(h13), "H14": _r2(h14),
        "H_TOTAL": _r2(h_total), "col_header_row": col_header_row,
    }


def parse_celcom(content: bytes) -> dict:
    """Parse a Celcom XLS file and return structured data."""
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, engine="xlrd")
    except Exception as e:
        raise CelcomParserError(f"לא ניתן לפתוח את הקובץ: {e}")

    header = _parse_header(df)
    data_start = header["col_header_row"] + 1

    rows = []
    for i in range(data_start, len(df)):
        row = df.iloc[i]

        col_a = str(row.iloc[0] if len(row) > 0 else "").strip()
        if col_a.startswith("סה"):
            break
        if row.isnull().all():
            break

        phone_raw = row.iloc[COL_PHONE] if COL_PHONE < len(row) else None
        phone = normalize_phone(phone_raw)

        ac = _to_dec(row.iloc[COL_AC] if COL_AC < len(row) else None)
        is_rollup = (not phone) and (ac < Decimal("-1"))
        if is_rollup:
            continue
        if not phone:
            continue

        name_f = str(row.iloc[COL_NAME] if COL_NAME < len(row) else "").strip()
        name_l = str(row.iloc[COL_SNAME] if COL_SNAME < len(row) else "").strip()
        for bad in ("nan", "None"):
            name_f = name_f.replace(bad, "").strip()
            name_l = name_l.replace(bad, "").strip()
        name = f"{name_f} {name_l}".strip()

        ce = _to_dec(row.iloc[COL_BEFORE_VAT] if COL_BEFORE_VAT < len(row) else None)
        cf = _to_dec(row.iloc[COL_EXEMPT] if COL_EXEMPT < len(row) else None)
        cg = _to_dec(row.iloc[COL_DEVICES] if COL_DEVICES < len(row) else None)

        # Amount = before_vat * 1.18 + exempt + devices
        amount = _r2(ce * VAT_RATE + cf + cg)
        if amount == Decimal("0"):
            continue

        rows.append({
            "phone":      phone,
            "name":       name,
            "amount":     amount,
            "before_vat": _r2(ce),
            "exempt":     _r2(cf),
            "devices":    _r2(cg),
        })

    sum_rows = _r2(sum(r["amount"] for r in rows))

    return {
        "inv_date":       header["inv_date"],
        "inv_num":        header["inv_num"],
        "customer_name":  header["customer_name"],
        "H11":            header["H11"],
        "H12":            header["H12"],
        "H13":            header["H13"],
        "H14":            header["H14"],
        "H_TOTAL":        header["H_TOTAL"],
        "rows":           rows,
        "sum_rows":       sum_rows,
        "balance_ok":     True,
    }
