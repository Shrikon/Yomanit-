# validation/validator.py – Validation Layer
from decimal import Decimal
from typing import List, Dict, Any


class ValidationError(Exception):
    pass


def validate_structure(rows: List[Dict]) -> None:
    """בדיקה מבנית — שדות חובה קיימים."""
    if not rows:
        raise ValidationError("קובץ ריק — אין שורות")
    for i, r in enumerate(rows):
        if not r.get("semel"):
            raise ValidationError(f"שורה {i+1}: חסר semel")


def validate_amounts(rows: List[Dict]) -> None:
    """בדיקת תקינות סכומים."""
    for i, r in enumerate(rows):
        try:
            Decimal(str(r.get("amount", 0)))
        except Exception:
            raise ValidationError(f"שורה {i+1}: סכום לא תקין: {r.get('amount')}")


def validate_balanced(lines: List[Dict]) -> None:
    """בדיקת איזון — חובה = זכות."""
    total_debit  = sum(Decimal(str(r["amount"])) for r in lines if r.get("side") == "debit")
    total_credit = sum(Decimal(str(r["amount"])) for r in lines if r.get("side") == "credit")
    if abs(total_debit - total_credit) > Decimal("0.01"):
        raise ValidationError(
            f"פקודה לא מאוזנת: חובה={total_debit} זכות={total_credit} הפרש={total_debit-total_credit}"
        )


def find_missing(rows: List[Dict], index: Dict) -> List[Dict]:
    """מחזיר שורות שאין להן index."""
    return [r for r in rows if r.get("semel") not in index]


def validate_all(rows: List[Dict], lines: List[Dict], index: Dict) -> Dict[str, Any]:
    """מריץ את כל הבדיקות ומחזיר תוצאה מרוכזת."""
    errors = []
    try:
        validate_structure(rows)
    except ValidationError as e:
        errors.append(str(e))
    try:
        validate_amounts(rows)
    except ValidationError as e:
        errors.append(str(e))
    missing = find_missing(rows, index)
    balance_error = None
    try:
        validate_balanced(lines)
    except ValidationError as e:
        balance_error = str(e)
        errors.append(str(e))
    return {
        "valid":    len(errors) == 0,
        "errors":   errors,
        "missing":  missing,
        "balanced": balance_error is None,
    }
