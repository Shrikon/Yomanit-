# routers/welfare.py – upload + preview + approve לרווחה
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from parsers.welfare import parse_welfare, apply_welfare_splits, WelfareParserError
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
import json

router = APIRouter()

WELFARE_TEMPLATE_NAME = "welfare"


# ─────────────────────────────────────────────
# POST /upload/welfare – preview
# ─────────────────────────────────────────────
@router.post("")
async def upload_welfare(
    file:            UploadFile = File(...),
    municipality_id: str        = Form(...),
    month:           int        = Form(None),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="קובץ ריק")

    # טען אינדקס מה-DB
    from main import database as _db
    try:
        welfare_tmpl = await _db.fetch_one(
            "SELECT id FROM templates WHERE name = 'welfare'", values={}
        )
        welfare_tmpl_id = str(welfare_tmpl["id"]) if welfare_tmpl else None
        
        index_rows = []
        if welfare_tmpl_id:
            index_rows = await _db.fetch_all(
                """SELECT key_value, account_code, description
                   FROM indexes
                   WHERE municipality_id = :muni AND template_id = :tmpl AND active = TRUE""",
                values={"muni": municipality_id, "tmpl": welfare_tmpl_id}
            )
        
        # בנה index_map: semel → {debit: account, credit: account}
        index_map = {}
        for row in index_rows:
            semel = row["key_value"]
            acct  = row["account_code"]
            side  = row["description"]  # 'debit' או 'credit'
            if semel not in index_map:
                index_map[semel] = {}
            if side in ("debit", "credit"):
                index_map[semel][side] = acct
        
        # אם אין אינדקס ב-DB – השתמש בברירת מחדל
        use_index = index_map if index_map else None
        
    except Exception:
        use_index = None

    try:
        parsed = parse_welfare(content, month=month, index_map=use_index)
    except WelfareParserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאת פרסור: {str(e)}")

    matched, missing = apply_welfare_splits(parsed)

    # בנה שורות תצוגה
    rows_out = []
    for r in matched:
        rows_out.append({
            "semel":       r["semel"],
            "name":        r["name"],
            "account":     r["account"],
            "amount":      r["amount"],
            "side":        r["side"],
            "description": r["description"],
            "status":      "ok",
        })
    for r in missing:
        rows_out.append({
            "semel":       r["semel"],
            "name":        r["name"],
            "account":     "",
            "amount":      float(r.get("chiuv_hodesh", 0) or r.get("mishrad", 0)),
            "side":        "unknown",
            "description": r["name"],
            "status":      "missing_index",
            "error":       r.get("error", ""),
        })

    can_approve = len(missing) == 0

    return {
        "filename":      file.filename,
        "template":      "welfare",
        "municipality":  parsed["municipality"],
        "period":        parsed["period"],
        "month":         parsed["month"],
        "total_rows":    len(rows_out),
        "matched":       len(matched),
        "missing":       len(missing),
        "rows":          rows_out,
        "total_debit":   parsed["total_debit"],
        "total_credit":  parsed["total_credit"],
        "can_approve":   can_approve,
        "missing_index": parsed["missing_index"],
    }


# ─────────────────────────────────────────────
# POST /upload/welfare/approve – יצירת פקודה
# ─────────────────────────────────────────────
from pydantic import BaseModel
from typing import List, Optional

class WelfareLineIn(BaseModel):
    semel:       str
    account:     str
    amount:      float
    side:        str   # debit | credit
    description: Optional[str] = None

class WelfareApproveIn(BaseModel):
    municipality_id: str
    period:          str
    month:           int
    year:            int = 2026
    source_file:     Optional[str] = None
    lines:           List[WelfareLineIn]


@router.post("/approve", status_code=201)
async def approve_welfare(payload: WelfareApproveIn):
    from main import database

    if not payload.lines:
        raise HTTPException(status_code=422, detail="אין שורות לאישור")

    # שלוף template_id
    tmpl = await database.fetch_one(
        "SELECT id FROM templates WHERE name = 'welfare'", values={}
    )
    if not tmpl:
        tmpl_id = str(uuid4())
        await database.execute(
            """INSERT INTO templates (id, name, display_name)
               VALUES (:id, 'welfare', 'רווחה')
               ON CONFLICT (name) DO NOTHING""",
            values={"id": tmpl_id}
        )
        tmpl = await database.fetch_one(
            "SELECT id FROM templates WHERE name = 'welfare'", values={}
        )

    template_id = str(tmpl["id"])
    period_str  = f"{payload.year}-{payload.month:02d}"

    # בדיקת כפילות
    existing = await database.fetch_one(
        """SELECT id, reference_num FROM journal_entries
           WHERE municipality_id = :muni AND template_id = :tmpl AND period = :period
             AND is_active = TRUE""",
        values={"muni": payload.municipality_id, "tmpl": template_id, "period": period_str}
    )
    if existing:
        raise HTTPException(status_code=409,
            detail=f"קיימת פקודה לתקופה {period_str}: {existing['reference_num']}")

    # חשב סכומים
    total_debit  = Decimal("0")
    total_credit = Decimal("0")
    for line in payload.lines:
        amt = Decimal(str(line.amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if line.side == "debit":
            total_debit += amt
        else:
            total_credit += amt

    # שלוף חשבון חו"ז משרד הרווחה
    ministry_setting = await database.fetch_one(
        """SELECT value FROM municipality_settings
           WHERE municipality_id = :muni AND template_name = 'welfare' AND key = 'ministry_account'""",
        values={"muni": payload.municipality_id}
    )
    ministry_account = ministry_setting["value"] if ministry_setting else "700000000"

    # חשב הפרש לחו"ז
    diff = (total_credit - total_debit).quantize(Decimal("0.01"), ROUND_HALF_UP)

    entry_id = str(uuid4())
    ref_num  = f"WLF-{period_str.replace('-','')}-{entry_id[:6].upper()}"

    async with database.transaction():
        await database.execute(
            """INSERT INTO journal_entries
               (id, municipality_id, template_id, period, reference_num,
                source_file, total_amount, status, source_type,
                source_period_month, source_period_year)
               VALUES (:id,:muni,:tmpl,:period,:ref,:src,:total,'draft','welfare',:month,:year)""",
            values={
                "id":    entry_id,
                "muni":  payload.municipality_id,
                "tmpl":  template_id,
                "period": period_str,
                "ref":   ref_num,
                "src":   payload.source_file,
                "total": float(total_debit),
                "month": payload.month,
                "year":  payload.year,
            }
        )

        # שורות פקודה
        for i, line in enumerate(payload.lines, 1):
            amt = Decimal(str(line.amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            await database.execute(
                """INSERT INTO journal_lines
                   (id,entry_id,line_num,account,description,debit,credit,reference,key_value)
                   VALUES (:id,:entry,:num,:acct,:desc,:debit,:credit,:ref,:key)""",
                values={
                    "id":     str(uuid4()),
                    "entry":  entry_id,
                    "num":    i,
                    "acct":   line.account,
                    "desc":   line.description or f"רווחה {line.semel}",
                    "debit":  float(amt) if line.side == "debit" else 0.0,
                    "credit": float(amt) if line.side == "credit" else 0.0,
                    "ref":    line.semel,
                    "key":    line.semel,
                }
            )

        # שורת חו"ז משרד הרווחה – ההפרש בין זכות לחובה
        if diff != Decimal("0"):
            await database.execute(
                """INSERT INTO journal_lines
                   (id,entry_id,line_num,account,description,debit,credit,reference,key_value)
                   VALUES (:id,:entry,:num,:acct,:desc,:debit,:credit,:ref,:key)""",
                values={
                    "id":     str(uuid4()),
                    "entry":  entry_id,
                    "num":    len(payload.lines) + 1,
                    "acct":   ministry_account,
                    "desc":   'חו"ז משרד הרווחה',
                    "debit":  float(diff) if diff > 0 else 0.0,
                    "credit": float(abs(diff)) if diff < 0 else 0.0,
                    "ref":    "חוז",
                    "key":    "חוז",
                }
            )

    return {
        "id":            entry_id,
        "reference_num": ref_num,
        "status":        "draft",
        "total_debit":   float(total_debit + (diff if diff > 0 else 0)),
        "total_credit":  float(total_credit + (abs(diff) if diff < 0 else 0)),
        "ministry_diff": float(diff),
        "ministry_account": ministry_account,
        "lines_count":   len(payload.lines) + (1 if diff != 0 else 0),
    }
