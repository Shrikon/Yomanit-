# parsers/celcom.py – פרסר סלקום
# מבוסס על ניתוח 15 קבצי XLS | עיריית דימונה
#
# כלל זהב: H_TOTAL = H11 + H12 + H13 + H14 (תקף בכל 15 הקבצים)
# מקור האמת: H_TOTAL מהכותרת בלבד

import io
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any

import pandas as pd


class CelcomParserError(Exception):
    pass


VAT_RATE    = Decimal("1.18")
BALANCE_TOL = Decimal("0.10")

COL_PHONE = 3
COL_NAME  = 4
COL_SNAME = 5
COL_AC    = 28
COL_CE    = 82
COL_CF    = 83
COL_CG    = 84
COL_CH    = 85


def normalize_phone(phone: Any) -> str:
    if phone is None:
        return ""

    phone = str(phone).strip()

    # סינון ערכים לא חוקיים
    if phone.lower() in ("nan", "none", "", "0"):
        return ""

    # הסרת רווחים ומקפים
    phone = phone.replace("-", "").replace(" ", "")

    # float: 505272448.0 → 505272448
    if "." in phone:
        phone = phone.split(".")[0]

    # קידומת בינלאומית ישראלית
    if phone.startswith("972"):
        phone = "0" + phone[3:]

    # הסרת אפסים מובילים
    phone = phone.lstrip("0")

    # חייב להיות מספרי
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


def _r2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_header(df: pd.DataFrame) -> dict:
    h11 = h12 = h13 = h14 = h_total = None
    col_header_row = None
    inv_date = inv_num = customer_name = ""

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
                if str(df.iloc[i, j] or "").strip() == "מספר לקוח":
                    col_header_row = i
                    break

    if h11 is None or h12 is None:
        raise CelcomParserError("לא נמצאו H11/H12 בכותרת")
    if h_total is None:
        raise CelcomParserError("לא נמצא H_TOTAL")
    if col_header_row is None:
        raise CelcomParserError("לא נמצאה שורת כותרות ('מספר לקוח')")

    h13 = h13 or Decimal("0")
    h14 = h14 or Decimal("0")

    calc = _r2(h11 + h12 + h13 + h14)
    if abs(calc - _r2(h_total)) > BALANCE_TOL:
        raise CelcomParserError(
            f"H_TOTAL לא מתאזן: H11+H12+H13+H14={calc} ≠ H_TOTAL={h_total}"
        )

    return {
        "inv_date": inv_date, "inv_num": inv_num, "customer_name": customer_name,
        "H11": _r2(h11), "H12": _r2(h12), "H13": _r2(h13), "H14": _r2(h14),
        "H_TOTAL": _r2(h_total), "col_header_row": col_header_row,
    }


def parse_celcom(content: bytes) -> dict:
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, engine="xlrd")
    except Exception as e:
        raise CelcomParserError(f"לא ניתן לפתוח את הקובץ: {e}")

    header = _parse_header(df)
    col_header_row = header["col_header_row"]
    data_start = col_header_row + 1

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

        # rollup: אין phone AND AC < -1
        is_rollup = (not phone) and (ac < Decimal("-1"))

        if is_rollup:
            rows.append({"phone": "", "name": "", "amount": Decimal("0"), "source": "", "is_rollup": True})
            continue

        # מסנן שורות ריקות ו-nan
        if not phone:
            continue

        name_f = str(row.iloc[COL_NAME]  if COL_NAME  < len(row) else "").strip()
        name_l = str(row.iloc[COL_SNAME] if COL_SNAME < len(row) else "").strip()
        for bad in ("nan", "None"):
            name_f = name_f.replace(bad, "").strip()
            name_l = name_l.replace(bad, "").strip()
        name = f"{name_f} {name_l}".strip()

        ce = _to_dec(row.iloc[COL_CE] if COL_CE < len(row) else None)
        cf = _to_dec(row.iloc[COL_CF] if COL_CF < len(row) else None)
        cg = _to_dec(row.iloc[COL_CG] if COL_CG < len(row) else None)

        amount = _r2(ce * VAT_RATE + cf + cg)

        parts = []
        if ce != Decimal("0"): parts.append("CE")
        if cf != Decimal("0"): parts.append("CF")
        if cg != Decimal("0"): parts.append("CG")
        source = "+".join(parts) if parts else "ZERO"

        if amount == Decimal("0"):
            continue

        rows.append({
            "phone": phone, "name": name, "amount": amount,
            "source": source, "is_rollup": False,
        })

    has_rollup = any(r["is_rollup"] for r in rows)
    file_type  = "A" if not has_rollup else ("C" if header["H13"] > Decimal("0") else "B")
    clean_rows = [r for r in rows if not r["is_rollup"]]
    sum_rows   = _r2(sum(r["amount"] for r in clean_rows))

    return {
        "file_type": file_type,
        "inv_date": header["inv_date"], "inv_num": header["inv_num"],
        "customer_name": header["customer_name"],
        "H11": header["H11"], "H12": header["H12"],
        "H13": header["H13"], "H14": header["H14"],
        "H_TOTAL": header["H_TOTAL"],
        "rows": clean_rows, "sum_rows": sum_rows, "balance_ok": True,
    }
