# parsers/electricity.py – פרסר חשמל BULLER – גרסת פרודקשן ראשונית

import io
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Tuple


class ElectricityParserError(Exception):
    """שגיאת מבנה – עוצרת קליטה"""
    pass


class ElectricityRowError(Exception):
    def __init__(self, row_num: int, contract: str, reason: str):
        self.row_num = row_num
        self.contract = contract
        self.reason = reason
        super().__init__(f"שורה {row_num} חוזה {contract}: {reason}")


def _decode(content: bytes) -> str:
    for enc in ("cp1255", "utf-8-sig", "iso-8859-8"):
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    raise ElectricityParserError("לא ניתן לקרוא את הקובץ – encoding לא מזוהה")


def _parse_amount(raw: str, row_num: int, contract: str) -> Decimal:
    cleaned = raw.replace(",", "").replace(" ", "").strip()
    if not cleaned:
        raise ElectricityRowError(row_num, contract, "חסר סכום")
    try:
        val = Decimal(cleaned)
    except InvalidOperation:
        raise ElectricityRowError(row_num, contract, f"סכום לא תקין: '{raw}'")
    # סכום שלילי = זיכוי לגיטימי
    return val


def _validate_buller_format(text: str) -> None:
    """בודק שהקובץ הוא BULLER חשמל ולא פורמט אחר"""
    # סימנים ייחודיים לקובץ BULLER חשמל
    ELECTRICITY_MARKERS = [
        "חשבון חוזה בן",
        'סכום כולל מע"מ',
        "כתובת אספקה",
    ]
    # סימנים לפורמטים אחרים שגויים
    WRONG_FORMAT_HINTS = {
        "מספר טלפון":   "נראה כקובץ בזק – יש להעלות בטאב בזק",
        "מספר מנוי":    "נראה כקובץ בזק – יש להעלות בטאב בזק",
        "ח.פ":          "נראה כקובץ ספק – פורמט לא מתאים לחשמל",
        "Invoice":      "נראה כקובץ באנגלית – פורמט לא מתאים לחשמל",
    }

    # בדוק רמזים לפורמט שגוי
    for hint, msg in WRONG_FORMAT_HINTS.items():
        if hint in text[:2000]:
            raise ElectricityParserError(f"פורמט קובץ שגוי: {msg}")

    # בדוק שיש לפחות סימן אחד של BULLER חשמל
    found = any(marker in text for marker in ELECTRICITY_MARKERS)
    if not found:
        raise ElectricityParserError(
            "פורמט קובץ לא מזוהה – יש להעלות קובץ BULLER חשמל בלבד (CSV מחברת החשמל)"
        )


def parse_buller(content: bytes) -> Dict[str, Any]:
    text  = _decode(content)
    lines = text.replace("\r", "").split("\n")

    if len(lines) < 7:
        raise ElectricityParserError("קובץ ריק או חלקי")

    # בדיקת פורמט – חייב להיות לפני כל עיבוד
    _validate_buller_format(text)

    # metadata
    customer_name = ""
    period = ""
    for line in lines[:5]:
        parts = [p.strip() for p in line.split(",")]
        for label in ("שם השותף עסקי  אב", "שם השותף עסקי אב"):
            if label in parts:
                try:
                    customer_name = parts[parts.index(label) + 1]
                except IndexError:
                    pass
        if "חודש" in parts:
            try:
                period = parts[parts.index("חודש") + 1]
            except IndexError:
                pass

    if not customer_name:
        raise ElectricityParserError("שם לקוח חסר בקובץ")

    # headers
    headers = [h.strip() for h in lines[5].split(",")]

    def col(name):
        try:
            return headers.index(name)
        except ValueError:
            return None

    col_contract  = col("חשבון חוזה בן")
    col_address   = col("כתובת אספקה")
    col_invoice   = col("מספר חשבונית")
    col_date_from = col("תחילת תקופת חשבון")
    col_date_to   = col("סיום תקופת חשבון")
    col_amount    = col('סכום כולל מע"מ')

    if col_contract is None:
        raise ElectricityParserError("עמודת 'חשבון חוזה בן' לא נמצאה")
    if col_amount is None:
        raise ElectricityParserError("עמודת 'סכום כולל מעמ' לא נמצאה")

    rows = []
    row_errors = []
    sum_details = Decimal("0")
    sum_credits = Decimal("0")
    total = Decimal("0")
    dates_from = []
    dates_to = []
    row_num = 0

    for line in lines[6:]:
        line = line.strip()
        if not line:
            continue

        parts = [p.strip() for p in line.split(",")]

        # שורת סיכום
        if line.startswith(",,,"):
            if 'סה"כ חיובים' in line or ("סה" in line and "ליום" not in line and "חיוב" not in line):
                try:
                    val = Decimal(parts[10].replace(",", "").strip())
                    if val > total:
                        total = val
                except (IndexError, InvalidOperation):
                    pass
            continue

        contract = parts[col_contract].strip() if col_contract < len(parts) else ""
        if not contract or not contract.isdigit():
            continue

        row_num += 1

        try:
            amount_raw = parts[col_amount] if col_amount < len(parts) else ""
            amount = _parse_amount(amount_raw, row_num, contract)
        except ElectricityRowError as e:
            row_errors.append({"row_num": e.row_num, "contract": e.contract, "reason": e.reason})
            continue

        if amount == 0:
            continue

        address = parts[col_address].strip()  if col_address  and col_address  < len(parts) else ""
        invoice = parts[col_invoice].strip()   if col_invoice  and col_invoice  < len(parts) else ""
        d_from  = parts[col_date_from].strip() if col_date_from and col_date_from < len(parts) else ""
        d_to    = parts[col_date_to].strip()   if col_date_to  and col_date_to  < len(parts) else ""

        if d_from: dates_from.append(d_from)
        if d_to:   dates_to.append(d_to)

        if amount < 0:
            sum_credits += abs(amount)
        sum_details += amount
        rows.append({
            "row_num":     row_num,
            "contract":    contract,
            "phone":       contract,
            "name":        address,
            "amount":      float(round(amount, 2)),
            "date":        d_from,
            "invoice":     invoice,
            "description": address,
            "has_index":   False,
            "account":     None,
        })

    if not rows:
        raise ElectricityParserError(
            "לא נמצאו שורות תקינות" +
            (f" ({len(row_errors)} שורות עם שגיאות)" if row_errors else "")
        )

    sum_f    = round(float(sum_details), 2)
    credits_f = round(float(sum_credits), 2)
    total_f  = float(total) if total > 0 else abs(sum_f)
    # השוואה: total_f (גרוס) = sum_f (נטו) + credits (זיכויים)
    diff     = round(abs(total_f - (sum_f + credits_f)), 2)

    if diff > 1.00:
        raise ElectricityParserError(
            f"הקובץ לא מאוזן: שורות={sum_f:,.2f} זיכויים={credits_f:,.2f} סה\"כ={total_f:,.2f} הפרש={diff:,.2f}"
        )

    return {
        "customer_name": customer_name,
        "period":        period,
        "date_from":     min(dates_from) if dates_from else "",
        "date_to":       max(dates_to)   if dates_to   else "",
        "rows":          rows,
        "row_errors":    row_errors,
        "total":         total_f,
        "sum_details":   sum_f,
        "balance_ok":    diff <= 1.00,
        "balance_diff":  diff,
    }


def apply_index_splits(rows: List[Dict], index_map: Dict[str, List[Dict]]) -> Tuple[List[Dict], List[Dict]]:
    """index lookup + פיצול תקציב לפי אחוז – Decimal בלבד למניעת סטיות כספיות"""
    from decimal import Decimal, ROUND_HALF_UP

    matched, missing = [], []

    for row in rows:
        contract = row["contract"]
        budgets  = index_map.get(contract)

        if not budgets:
            missing.append({**row, "has_index": False, "account": None,
                            "error": f"חוזה {contract} לא נמצא באינדקס"})
            continue

        if len(budgets) == 1:
            matched.append({**row, "has_index": True, "account": budgets[0]["account"]})
            continue

        # המרה ל-Decimal – הכרחי לחישוב כספי מדויק
        total_amount = Decimal(str(row["amount"]))
        allocated    = Decimal("0")

        for i, budget in enumerate(budgets):
            percent = Decimal(str(budget.get("percent", 100)))
            if i < len(budgets) - 1:
                part = (total_amount * percent / Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP)
                allocated += part
            else:
                # שורה אחרונה – השארית המדויקת למניעת הפרש עיגול
                part = total_amount - allocated

            matched.append({
                **row,
                "has_index":   True,
                "account":     budget["account"],
                "amount":      float(part),
                "description": f"{row['description']} ({int(percent)}%)",
            })

    return matched, missing
