# parsers/celcom.py – פרסר סלקום
#
# מבנה הקובץ:
#   rows 0-13:  כותרת (שם חברה, חשבונית, תאריך, סך לתשלום)
#   row ~15:    כותרות עמודות (מזוהות לפי "מספר לקוח")
#   rows data:  נתוני מנויים עד שורת סיכום
#
# col3  = מספר סלקום | col85 = סה"כ כולל מע"מ (הסכום לפקודה)
# הצלבה: sum(col85) == סך החשבונית לתשלום מהכותרת

import io
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any

import pandas as pd


class CelcomParserError(Exception):
    pass


BALANCE_TOL = Decimal("0.10")

COL_PHONE = 3
COL_NAME  = 4
COL_SNAME = 5
COL_CE    = 82  # סה"כ לפני מע"מ
COL_CF    = 83  # סה"כ פטור מע"מ
COL_CG    = 84  # סה"כ חיובים/זיכויים כוללי מע"מ
VAT_RATE  = Decimal("1.18")


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
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def _r2(d) -> Decimal:
    if not isinstance(d, Decimal):
        d = Decimal(str(d))
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_header(df: pd.DataFrame) -> dict:
    """Parse header rows for invoice metadata."""
    h_total = None
    inv_date = inv_num = customer_name = ""
    col_header_row = None

    for i in range(0, min(25, len(df))):
        label = str(df.iloc[i, 6] if len(df.columns) > 6 else "").strip()
        val   = df.iloc[i, 7] if len(df.columns) > 7 else None

        if "לתשלום" in label and "סך" in label:
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

    if h_total is None:
        raise CelcomParserError("לא נמצא סך החשבונית לתשלום בכותרת")
    if col_header_row is None:
        col_header_row = 15

    return {
        "inv_date": inv_date, "inv_num": inv_num,
        "customer_name": customer_name,
        "H_TOTAL": _r2(h_total), "col_header_row": col_header_row,
    }


def parse_celcom(content: bytes) -> dict:
    """Parse a Celcom XLS file. Returns rows with col85 as amount."""
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

        name_f = str(row.iloc[COL_NAME] if COL_NAME < len(row) else "").strip()
        name_l = str(row.iloc[COL_SNAME] if COL_SNAME < len(row) else "").strip()
        for bad in ("nan", "None"):
            name_f = name_f.replace(bad, "").strip()
            name_l = name_l.replace(bad, "").strip()
        name = f"{name_f} {name_l}".strip()

        ce = _to_dec(row.iloc[COL_CE] if COL_CE < len(row) else None)
        cf = _to_dec(row.iloc[COL_CF] if COL_CF < len(row) else None)
        cg = _to_dec(row.iloc[COL_CG] if COL_CG < len(row) else None)
        amount = _r2(ce * VAT_RATE + cf + cg)
        if amount == Decimal("0"):
            continue

        rows.append({
            "phone":  phone,  # empty for adjustment rows
            "name":   name or "שורת התאמה",
            "amount": amount,
        })

    sum_rows = _r2(sum(r["amount"] for r in rows))
    h_total = header["H_TOTAL"]

    # Cross-validation (warning only — some files have structural differences)
    balance_ok = abs(sum_rows - h_total) <= BALANCE_TOL
    if not balance_ok:
        print(f"[CELCOM] Balance warning: sum(col85)={sum_rows} vs H_TOTAL={h_total} "
              f"diff={sum_rows - h_total}", flush=True)

    return {
        "inv_date":      header["inv_date"],
        "inv_num":       header["inv_num"],
        "customer_name": header["customer_name"],
        "H_TOTAL":       h_total,
        "rows":          rows,
        "sum_rows":      sum_rows,
        "balance_ok":    balance_ok,
    }
