# routers/upload.py – קליטת קבצים + פרסר בזק

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
import pandas as pd
import io
import re
from typing import Optional
from uuid import UUID

router = APIRouter()

def get_db():
    import db
    return db

# =============================================
# BEZEQ PARSER
# =============================================

BEZEQ_COLUMN_ALIASES = {
    "phone":   ["phone","טלפון","מספר טלפון","מס טלפון","tel","telephone","מספר מנוי","מנוי","subscriber_id","מספר_מנוי"],
    "name":    ["name","שם","שם מנוי","subscriber","שם לקוח","שם_מנוי","שם_לקוח"],
    "amount":  ["amount","סכום","total","חיוב","לתשלום","סכום כולל מע\"מ","סכום כולל מעמ","סכום כולל","סכום לתשלום"],
    "date":    ["date","תאריך","invoice_date","תאריך חשבונית","תאריך חיוב","תאריך_חיוב"],
    "invoice": ["invoice","חשבונית","מספר חשבונית","inv","invoice_id","מזהה","מספר_חשבונית","מספר חשבונית"],
}

BEZEQ_SHEET_NAMES = ["פרטי מנוי", "Sheet1", "bezeq", "data", "נתונים", "חיובים"]

def normalize_phone(phone: str) -> str:
    """Normalize Israeli phone numbers. Preserves special formats like 1800-XXXXXX."""
    phone = str(phone).strip()
    # מספרי 1800 / 1700 / 1599 – לא לנרמל
    if re.match(r"^1[5789]", phone.replace("-", "")):
        return phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 9 and digits.startswith("0"):
        return f"{digits[:2]}-{digits[2:]}"
    if len(digits) == 10 and digits.startswith("0"):
        return f"{digits[:3]}-{digits[3:]}"
    return phone

def find_column(df: pd.DataFrame, aliases: list[str]) -> Optional[str]:
    """Find a column by any of its known aliases (case-insensitive)."""
    for col in df.columns:
        if col.strip().lower() in [a.lower() for a in aliases]:
            return col
    return None

# =============================================
# UNIVERSAL BEZEQ PARSER
# תומך בכל מבני חשבון – גמיש לחלוטין
# =============================================

EXTRA_SHEETS_CONFIG = {
    "סכומים מחשבוניות קודמות": {
        "amount_col": "סכום כולל מע''מ",
        "desc_col":   "תיאור מלולי",
        "phone_col":  "מספר מנוי",
        "use_vat":    False,
    },
    "חיובים וזיכויים למשלם": {
        "amount_col": "סכום חיוב",
        "vat_col":    'אחוז מע"מ',
        "desc_col":   "תיאור חיוב",
        "phone_col":  "מספר מנוי",
        "use_vat":    True,
    },
    # "חיובים וזיכויים" ללא "למשלם" = פירוט שורות, לא חיובים נוספים - לא לקלוט!
}

def parse_bezeq_universal(content: bytes) -> dict:
    """Universal Bezeq parser – handles any number of sheets."""
    result = {
        "invoice_total": 0.0,
        "invoice_num":   "",
        "date_from":     "",
        "date_to":       "",
        "rows":          [],
        "extra_lines":   [],
        "sum_details":   0.0,
    }
    try:
        xl  = pd.ExcelFile(io.BytesIO(content))

        # --- סיכום חשבון ---
        if "סיכום חשבון" in xl.sheet_names:
            df = xl.parse("סיכום חשבון")
            def gcol(names):
                for n in names:
                    c = find_column(df, [n])
                    if c: return df.iloc[0][c]
                return None
            result["invoice_total"] = float(gcol(["סך הכל חשבון", "סך הכל חשבונית"]) or 0)
            result["date_from"]     = str(gcol(["תאריך תחילת חשבון"]) or "").strip()
            result["date_to"]       = str(gcol(["תאריך סיום חשבון"])  or "").strip()
            inv_raw = str(gcol(["מספר חשבונית"]) or "").replace("'","").strip()
            digits  = re.sub(r"\D", "", inv_raw)
            result["invoice_num"] = digits[-7:] if len(digits) >= 7 else digits
            # שם לקוח מהחשבונית
            result["customer_name"] = str(gcol(["שם לקוח", "שם_לקוח", "customer"]) or "").strip()

        # --- פרטי מנוי ---
        sheet_name = "פרטי מנוי"
        if sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name)
            col_phone  = find_column(df, ["מספר מנוי", "phone", "טלפון"])
            col_amount = find_column(df, ['סכום כולל מע"מ', "סכום כולל מעמ", "amount"])
            if col_phone and col_amount:
                for _, row in df.iterrows():
                    phone  = normalize_phone(str(row.get(col_phone, "") or ""))
                    amount = float(str(row.get(col_amount, 0) or 0).replace(",","").replace("₪","") or 0)
                    if not phone or amount <= 0:
                        continue
                    result["rows"].append({
                        "row_num": len(result["rows"]) + 2,
                        "phone":   phone,
                        "name":    "",
                        "amount":  round(amount, 2),
                        "date":    "",
                        "invoice": result["invoice_num"],
                    })
                    result["sum_details"] += amount

        # --- גליונות נוספים ---
        for sname, cfg in EXTRA_SHEETS_CONFIG.items():
            if sname not in xl.sheet_names:
                continue
            df = xl.parse(sname)
            acol = find_column(df, [cfg["amount_col"]])
            if not acol:
                continue
            dcol = find_column(df, [cfg.get("desc_col","")]) if cfg.get("desc_col") else None
            pcol = find_column(df, [cfg.get("phone_col","")]) if cfg.get("phone_col") else None
            vcol = find_column(df, [cfg.get("vat_col","")]) if cfg.get("vat_col") else None

            for _, row in df.iterrows():
                base = float(str(row.get(acol, 0) or 0).replace(",","") or 0)
                if base == 0:
                    continue
                if cfg.get("use_vat") and vcol and row.get(vcol):
                    amount = round(base * (1 + float(row[vcol]) / 100), 2)
                else:
                    amount = round(base, 2)
                desc  = str(row.get(dcol, "") or "") if dcol else ""
                phone = str(row.get(pcol, "") or "") if pcol else ""
                result["extra_lines"].append({
                    "phone":       phone,
                    "amount":      amount,
                    "description": desc,
                    "sheet":       sname,
                })
                result["sum_details"] += amount

        result["sum_details"]  = round(result["sum_details"], 2)
        result["balance_ok"]   = abs(result["sum_details"] - result["invoice_total"]) <= 0.10
        result["balance_diff"] = round(abs(result["sum_details"] - result["invoice_total"]), 2)
    except Exception as e:
        result["error"] = str(e)
    return result

def get_bezeq_summary(content: bytes) -> dict:
    r = parse_bezeq_universal(content)
    return {"total": r["invoice_total"], "date_from": r["date_from"], "date_to": r["date_to"]}

def get_bezeq_invoice_total(content: bytes) -> float:
    return parse_bezeq_universal(content)["invoice_total"]

def get_bezeq_invoice_number(content: bytes) -> str:
    return parse_bezeq_universal(content)["invoice_num"]

def parse_bezeq(df: pd.DataFrame) -> list[dict]:
    """Parse a Bezeq CSV/Excel into normalized rows."""
    rows = []
    col_phone   = find_column(df, BEZEQ_COLUMN_ALIASES["phone"])
    col_name    = find_column(df, BEZEQ_COLUMN_ALIASES["name"])
    col_amount  = find_column(df, BEZEQ_COLUMN_ALIASES["amount"])
    col_date    = find_column(df, BEZEQ_COLUMN_ALIASES["date"])
    col_invoice = find_column(df, BEZEQ_COLUMN_ALIASES["invoice"])

    if not col_phone or not col_amount:
        raise ValueError("הקובץ חייב להכיל עמודות טלפון וסכום")

    for idx, row in df.iterrows():
        phone  = normalize_phone(row.get(col_phone, ""))
        amount = float(str(row.get(col_amount, 0)).replace(",", "").replace("₪", "") or 0)

        if not phone or amount <= 0:
            continue

        rows.append({
            "row_num":  idx + 2,
            "phone":    phone,
            "name":     str(row.get(col_name,    ""))   if col_name    else "",
            "amount":   round(amount, 2),
            "date":     str(row.get(col_date,    ""))   if col_date    else "",
            "invoice":  str(row.get(col_invoice, ""))   if col_invoice else "",
        })
    return rows

# =============================================
# ENDPOINT: POST /upload
# =============================================

@router.post("")
async def upload_file(
    file:            UploadFile = File(...),
    municipality_id: str        = Form(...),
    template:        str        = Form("bezeq"),   # bezeq | electricity | welfare
):
    """
    Upload a Bezeq/electricity/welfare file.
    Returns parsed rows + index match status.
    """
    print("UPLOAD CALLED", flush=True)
    print("UPLOAD STARTED", flush=True)
    content = await file.read()
    filename = file.filename or ""
    print(f"FILE: {filename}, SIZE: {len(content)}", flush=True)
    print("FILE READ:", filename, len(content), flush=True)

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
        elif filename.endswith((".xlsx", ".xls")):
            xl = pd.ExcelFile(io.BytesIO(content))
            df = None
            for sheet in BEZEQ_SHEET_NAMES:
                if sheet in xl.sheet_names:
                    df = xl.parse(sheet)
                    break
            if df is None:
                df = xl.parse(xl.sheet_names[0])
        else:
            raise HTTPException(status_code=400, detail="פורמט לא נתמך – שלח CSV או Excel")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"שגיאה בקריאת הקובץ: {str(e)}")

    # --- Parse ---
    parsed: dict = {}
    if template == "bezeq":
        if filename.endswith((".xlsx", ".xls")):
            # Excel - use universal parser
            parsed = parse_bezeq_universal(content)
            rows = parsed["rows"]
        else:
            # CSV - use basic parser
            try:
                rows = parse_bezeq(df)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail=f"תבנית '{template}' עדיין לא נתמכת")

    # --- בדיקת שיוך קובץ לרשות ---
    customer_name = parsed.get("customer_name", "") if parsed else ""
    if customer_name:
        muni_row = await get_db().fetch_one(
            "SELECT name FROM municipalities WHERE id = :id",
            values={"id": municipality_id}
        )
        if muni_row:
            muni_name = muni_row["name"] if isinstance(muni_row, dict) else muni_row["name"]
            # בדוק אם יש מילה משותפת בין שם הלקוח לשם הרשות
            # נרמל שמות - הסר קידומות ומקפים
            import re as _re
            def normalize(s):
                s = s.replace("מ.מ","").replace("מ.א","").replace("עיריית","").replace("עירית","")
                s = s.replace("מועצה","").replace("אזורית","").replace("מקומית","").replace("-"," ")
                return s.strip()
            muni_clean = normalize(muni_name)
            customer_clean = normalize(customer_name)
            muni_words = {w.strip() for w in muni_clean.split() if len(w.strip()) > 1}
            customer_words = {w.strip() for w in customer_clean.split() if len(w.strip()) > 1}
            if muni_words and not muni_words.intersection(customer_words):
                raise HTTPException(
                    status_code=400,
                    detail=f"הקובץ שייך ל'{customer_name}' ולא ל'{muni_name}'. אנא העלה קובץ של הרשות הנכונה."
                )

    # --- Index lookup (query DB) ---
    async def lookup_index(key: str):
        return await get_db().fetch_one(
            """SELECT i.account_code, i.connection_name
               FROM   indexes i
               JOIN   templates t ON t.id = i.template_id
               WHERE  i.municipality_id = :muni
                 AND  t.name            = :tmpl
                 AND  i.key_value       = :key
                 AND  i.active          = TRUE""",
            values={"muni": municipality_id, "tmpl": template, "key": key},
        )

    matched, missing = [], []
    for row in rows:
        idx = await lookup_index(row["phone"])
        if idx:
            matched.append({**row, "account": idx["account_code"],
                            "description": idx["connection_name"] or "",
                            "has_index": True})
        else:
            missing.append({**row, "account": None,
                            "description": None, "has_index": False,
                            "error": f"מספר מנוי {row['phone']} לא נמצא באינדקס"})

    # --- שליפת נתוני חשבונית (אוניברסלי) ---
    invoice_total = 0.0
    invoice_num   = ""
    date_from     = ""
    date_to       = ""
    extra_lines: list = []

    if filename.endswith((".xlsx", ".xls")):
        invoice_total = parsed["invoice_total"]
        invoice_num   = parsed["invoice_num"]
        date_from     = parsed["date_from"]
        date_to       = parsed["date_to"]
        extra_lines   = parsed["extra_lines"]

    # --- Index lookup for extra_lines ---
    enriched_extras = []
    for el in extra_lines:
        key = (el["phone"] or "").strip() or "00000000000"
        idx = await lookup_index(key)
        amt = el.get("amount", 0)
        try:
            amt = float(amt)
            if amt != amt: amt = 0.0  # NaN check
        except (TypeError, ValueError):
            amt = 0.0
        enriched_extras.append({
            **el,
            "amount": amt,
            "account": idx["account_code"] if idx else None,
            "has_index": bool(idx),
        })
    extra_lines = enriched_extras

    sum_details = round(sum(r["amount"] for r in rows), 2)
    # הוסף גם extra_lines לסכום
    sum_details_total = round(sum_details + sum(l["amount"] for l in extra_lines), 2)
    diff       = round(abs(invoice_total - sum_details_total), 2) if invoice_total else 0
    balance_ok = diff <= 0.10

    return {
        "filename":      filename,
        "template":      template,
        "total_rows":    len(rows),
        "matched":       len(matched),
        "missing":       len(missing),
        "rows":          matched + missing,
        "extra_lines":   extra_lines,
        "sum_details":   sum_details_total,
        "invoice_total": invoice_total,
        "invoice_num":   invoice_num,
        "date_from":     date_from,
        "date_to":       date_to,
        "balance_diff":  diff,
        "balance_ok":    balance_ok,
    }
