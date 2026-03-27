# routers/electricity.py – upload + preview + approve עם import_batches
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from parsers.electricity import parse_buller, ElectricityParserError
from parsers.electricity_index import lookup_and_split
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
import hashlib, json

router = APIRouter()

ELEC_TEMPLATE_ID = "5594291d-2a5f-4b6c-846a-bed1290388b1"
HE_MONTHS = {
    'ינואר':'01','פברואר':'02','מרץ':'03','אפריל':'04',
    'מאי':'05','יוני':'06','יולי':'07','אוגוסט':'08',
    'ספטמבר':'09','אוקטובר':'10','נובמבר':'11','דצמבר':'12'
}

def _parse_period(raw: str):
    """המר 'ספטמבר 2025' ל-(9, 2025)"""
    parts = raw.strip().split()
    if len(parts) == 2 and parts[0] in HE_MONTHS:
        return int(HE_MONTHS[parts[0]]), int(parts[1])
    # fallback: YYYY-MM
    if len(raw) >= 7 and raw[4] == '-':
        return int(raw[5:7]), int(raw[:4])
    return None, None


# ─────────────────────────────────────────────
# POST /upload/electricity  – preview + שמירת batch
# ─────────────────────────────────────────────
@router.post("")
async def upload_electricity(
    file:            UploadFile = File(...),
    municipality_id: str        = Form(...),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="קובץ ריק")

    # hash למניעת כפילות
    file_hash = hashlib.sha256(content).hexdigest()

    # 1. פרסור
    try:
        parsed = parse_buller(content)
    except ElectricityParserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאת פרסור: {str(e)}")

    # 2. index lookup
    try:
        import db
        from main import database

        tmpl = await database.fetch_one(
            "SELECT id FROM templates WHERE name = 'electricity'", values={}
        )
        if not tmpl:
            raise HTTPException(status_code=500, detail="תבנית חשמל לא נמצאה ב-DB")

        template_id = str(tmpl["id"])
        matched, missing, index_map = await lookup_and_split(
            parsed["rows"], database, municipality_id, template_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאת אינדקס: {str(e)}")

    # 3. בנה preview
    contracts_preview = _build_contracts_preview(matched, missing)
    period_month, period_year = _parse_period(parsed["period"])

    has_missing = len(missing) > 0
    has_errors  = len(parsed.get("row_errors", [])) > 0
    can_approve = not has_missing and not has_errors and parsed["balance_ok"]

    rows_out = sorted(
        [_make_row(r, "ok", r.get("account")) for r in matched] +
        [_make_row(r, "missing_index", None, r.get("error", "חסר באינדקס")) for r in missing],
        key=lambda x: x["row_num"]
    )

    # 4. שמור batch ב-DB (רק אם ניתן לפרסר)
    batch_id = None
    if period_month and period_year:
        try:
            batch_id = await _save_batch(
                database=database,
                municipality_id=municipality_id,
                template_id=template_id,
                file_name=file.filename,
                file_hash=file_hash,
                period_month=period_month,
                period_year=period_year,
                parsed=parsed,
                matched=matched,
                missing=missing,
                contracts_preview=contracts_preview,
                rows_out=rows_out,
            )
        except Exception as e:
            # batch save נכשל – לא חוסם את ה-preview
            import logging
            logging.warning(f"Batch save failed (non-critical): {e}")

    return {
        "filename":         file.filename,
        "template":         "electricity",
        "template_id":      template_id,
        "batch_id":         batch_id,
        "customer_name":    parsed["customer_name"],
        "period":           parsed["period"],
        "period_month":     period_month,
        "period_year":      period_year,
        "date_from":        parsed["date_from"],
        "date_to":          parsed["date_to"],
        "total_rows":       len(rows_out),
        "matched":          len(matched),
        "missing":          len(missing),
        "row_errors":       parsed.get("row_errors", []),
        "rows":             rows_out,
        "contracts":        contracts_preview,
        "sum_details":      parsed["sum_details"],
        "invoice_total":    parsed["total"],
        "balance_ok":       parsed["balance_ok"],
        "balance_diff":     parsed["balance_diff"],
        "can_approve":      can_approve,
    }


async def _save_batch(database, municipality_id, template_id, file_name, file_hash,
                      period_month, period_year, parsed, matched, missing,
                      contracts_preview, rows_out):
    """שומר batch + lines ב-DB, מחזיר batch_id"""

    # בדוק אם כבר קיים batch מאושר לתקופה זו
    existing_approved = await database.fetch_one(
        """SELECT id FROM import_batches
           WHERE municipality_id = :muni AND template_id = :tmpl
             AND period_year = :year AND period_month = :month
             AND status = 'approved' AND is_active = TRUE""",
        values={"muni": municipality_id, "tmpl": template_id,
                "year": period_year, "month": period_month}
    )
    # אם קיים approved – עדיין נשמור כ-version חדש (לא חוסם)

    # batch_version
    ver_row = await database.fetch_one(
        """SELECT COALESCE(MAX(batch_version), 0) AS v FROM import_batches
           WHERE municipality_id = :muni AND template_id = :tmpl
             AND period_year = :year AND period_month = :month""",
        values={"muni": municipality_id, "tmpl": template_id,
                "year": period_year, "month": period_month}
    )
    version = (ver_row["v"] or 0) + 1

    batch_id = str(uuid4())

    # snapshot מלא
    snapshot = {
        "customer_name": parsed["customer_name"],
        "sum_details":   parsed["sum_details"],
        "total":         parsed["total"],
        "contracts":     contracts_preview[:50],  # מקסימום 50 לסnapshot
    }

    async with database.transaction():
        await database.execute(
            """INSERT INTO import_batches
               (id, municipality_id, template_id, source_file_name,
                period_month, period_year, batch_version,
                status, total_amount, total_rows, matched_rows, missing_rows,
                preview_snapshot)
               VALUES (:id, :muni, :tmpl, :fname,
                       :month, :year, :ver,
                       'preview_ready', :total, :rows, :matched, :missing,
                       :preview)""",
            values={
                "id":      batch_id,
                "muni":    municipality_id,
                "tmpl":    template_id,
                "fname":   file_name,
                "month":   period_month,
                "year":    period_year,
                "ver":     version,
                "total":   parsed["sum_details"],
                "rows":    len(rows_out),
                "matched": len(matched),
                "missing": len(missing),
                "preview": json.dumps(snapshot, ensure_ascii=False),
            }
        )

        # שורות קליטה
        for row in rows_out:
            await database.execute(
                """INSERT INTO import_batch_lines
                   (id, batch_id, source_key_value, source_description,
                    raw_amount, matched, missing_reason, account_code, final_amount)
                   VALUES (:id, :bid, :key, :desc,
                           :raw, :matched, :reason, :acct, :final)""",
                values={
                    "id":      str(uuid4()),
                    "bid":     batch_id,
                    "key":     row["contract"],
                    "desc":    row["description"],
                    "raw":     row["amount"],
                    "matched": row["status"] == "ok",
                    "reason":  row.get("error") if row["status"] != "ok" else None,
                    "acct":    row.get("account"),
                    "final":   row["amount"] if row["status"] == "ok" else None,
                }
            )

    return batch_id


def _make_row(row, status, account, error=""):
    return {
        "row_num":     row["row_num"],
        "contract":    row["contract"],
        "description": row["description"],
        "amount":      row["amount"],
        "date":        row.get("date", ""),
        "invoice":     row.get("invoice", ""),
        "account":     account,
        "status":      status,
        "error":       error,
    }


def _build_contracts_preview(matched, missing):
    by_contract: dict = {}
    for row in matched:
        c = row["contract"]
        if c not in by_contract:
            by_contract[c] = {"contract": c, "lines": [], "status": "ok"}
        desc = row.get("description", "")
        pct = None
        if "(" in desc and "%" in desc:
            try:
                pct = float(desc.split("(")[-1].replace("%)", "").strip())
            except ValueError:
                pass
        by_contract[c]["lines"].append({
            "account":     row["account"],
            "percent":     pct,
            "amount":      row["amount"],
            "description": desc,
        })
    for c, data in by_contract.items():
        data["original_amount"] = round(sum(l["amount"] for l in data["lines"]), 2)
    for row in missing:
        c = row["contract"]
        by_contract[c] = {
            "contract":        c,
            "original_amount": row["amount"],
            "lines":           [],
            "status":          "missing_index",
            "error":           row.get("error", "חסר באינדקס"),
        }
    return list(by_contract.values())


# ─────────────────────────────────────────────
# POST /upload/electricity/approve
# ─────────────────────────────────────────────
from pydantic import BaseModel
from typing import List, Optional

class ApproveLineIn(BaseModel):
    account:     str
    amount:      float
    description: Optional[str] = None
    key_value:   Optional[str] = None

class ApproveIn(BaseModel):
    municipality_id: str
    template_id:     str
    period:          str
    batch_id:        Optional[str] = None
    source_file:     Optional[str] = None
    date_from:       Optional[str] = None
    date_to:         Optional[str] = None
    invoice_total:   float
    lines:           List[ApproveLineIn]


@router.post("/approve", status_code=201)
async def approve_electricity(payload: ApproveIn):
    from main import database

    # ── Idempotent: אם batch כבר approved → החזר journal קיים ──
    if payload.batch_id:
        batch = await database.fetch_one(
            "SELECT * FROM import_batches WHERE id = :id",
            values={"id": payload.batch_id}
        )
        if batch and batch["status"] == "approved" and batch["journal_entry_id"]:
            return {
                "id":             batch["journal_entry_id"],
                "reference_num":  "כבר קיים",
                "status":         "approved",
                "already_exists": True,
            }

    if not payload.lines:
        raise HTTPException(status_code=422, detail="אין שורות לאישור")

    # ולידציה Decimal
    total_net = Decimal("0")
    for i, line in enumerate(payload.lines):
        if not line.account.strip():
            raise HTTPException(status_code=422, detail=f"שורה {i+1}: קוד חשבון ריק")
        if line.amount == 0:
            raise HTTPException(status_code=422, detail=f"שורה {i+1}: סכום אפס")
        total_net += Decimal(str(line.amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)

    expected = Decimal(str(payload.invoice_total)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    if abs(total_net - expected) > Decimal("0.10"):
        raise HTTPException(status_code=422,
            detail=f"פקודה לא מאוזנת: שורות={total_net} חשבונית={expected}")

    # בדיקת כפילות תקופה
    existing = await database.fetch_one(
        """SELECT id, reference_num FROM journal_entries
           WHERE municipality_id = :muni AND template_id = :tmpl AND period = :period
             AND is_active = TRUE""",
        values={"muni": payload.municipality_id, "tmpl": payload.template_id,
                "period": payload.period}
    )
    if existing:
        raise HTTPException(status_code=409,
            detail=f"קיימת פקודה לתקופה {payload.period}: {existing['reference_num']}")

    # חשבון ספק
    vendor_row = await database.fetch_one(
        """SELECT value FROM municipality_settings
           WHERE municipality_id = :muni AND template_name = 'electricity' AND key = 'vendor_account'""",
        values={"muni": payload.municipality_id}
    )
    vendor_account = vendor_row["value"] if vendor_row and vendor_row["value"] else "7000000000"

    notes = json.dumps({
        "date_from": payload.date_from or "",
        "date_to":   payload.date_to or "",
    }, ensure_ascii=False)

    entry_id = str(uuid4())
    ref_num  = f"ELEC-{payload.period.replace('-','')}-{entry_id[:6].upper()}"

    # חלץ month/year מהתקופה
    try:
        period_year  = int(payload.period[:4])
        period_month = int(payload.period[5:7])
    except Exception:
        period_year = period_month = None

    async with database.transaction():
        await database.execute(
            """INSERT INTO journal_entries
               (id, municipality_id, template_id, period, reference_num,
                source_file, total_amount, notes, status,
                source_batch_id, source_type, source_period_month, source_period_year)
               VALUES (:id,:muni,:tmpl,:period,:ref,:src,:total,:notes,'draft',
                       :bid,:stype,:smonth,:syear)""",
            values={
                "id":     entry_id,
                "muni":   payload.municipality_id,
                "tmpl":   payload.template_id,
                "period": payload.period,
                "ref":    ref_num,
                "src":    payload.source_file,
                "total":  float(total_net),
                "notes":  notes,
                "bid":    payload.batch_id,
                "stype":  "electricity",
                "smonth": period_month,
                "syear":  period_year,
            }
        )

        for i, line in enumerate(payload.lines, 1):
            amount_d = Decimal(str(line.amount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            await database.execute(
                """INSERT INTO journal_lines
                   (id,entry_id,line_num,account,description,debit,credit,reference,key_value)
                   VALUES (:id,:entry,:num,:acct,:desc,:debit,:credit,:ref,:key)""",
                values={
                    "id":     str(uuid4()),
                    "entry":  entry_id,
                    "num":    i,
                    "acct":   line.account,
                    "desc":   line.description or "",
                    "debit":  float(amount_d) if line.amount > 0 else 0.0,
                    "credit": float(abs(amount_d)) if line.amount < 0 else 0.0,
                    "ref":    None,
                    "key":    line.key_value or "",
                }
            )

        # שורת זכות
        await database.execute(
            """INSERT INTO journal_lines
               (id,entry_id,line_num,account,description,debit,credit,reference,key_value)
               VALUES (:id,:entry,:num,:acct,:desc,:debit,:credit,:ref,:key)""",
            values={
                "id":     str(uuid4()),
                "entry":  entry_id,
                "num":    len(payload.lines) + 1,
                "acct":   vendor_account,
                "desc":   "חשמל - חשבון חודשי",
                "debit":  0.0,
                "credit": float(total_net),
                "ref":    None,
                "key":    "",
            }
        )

        # עדכן batch → approved
        if payload.batch_id:
            from datetime import datetime, timezone
            await database.execute(
                """UPDATE import_batches
                   SET status = 'approved', journal_entry_id = :jid,
                       approved_at = :now, updated_at = :now
                   WHERE id = :bid AND status = 'preview_ready'""",
                values={"bid": payload.batch_id, "jid": entry_id,
                        "now": datetime.now(timezone.utc)}
            )

    return {
        "id":            entry_id,
        "reference_num": ref_num,
        "status":        "draft",
        "total":         float(total_net),
        "lines_count":   len(payload.lines) + 1,
        "batch_id":      payload.batch_id,
    }
