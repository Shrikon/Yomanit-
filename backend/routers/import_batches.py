# routers/import_batches.py – ניהול באצ'י קליטה
# ספרינט 1: import_batches + approve idempotent

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from decimal import Decimal, ROUND_HALF_UP
import hashlib, json
import db; database = db

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class BatchLineIn(BaseModel):
    source_key_value:   str
    source_description: Optional[str] = None
    raw_amount:         float
    matched:            bool
    missing_reason:     Optional[str] = None
    account_code:       Optional[str] = None
    split_percent:      Optional[float] = None
    final_amount:       Optional[float] = None
    raw_payload:        Optional[dict] = None

class BatchCreateIn(BaseModel):
    municipality_id:  str
    template_id:      str
    source_file_name: str
    file_content_b64: Optional[str] = None  # לחישוב hash
    period_month:     int
    period_year:      int
    total_amount:     float
    total_rows:       int
    matched_rows:     int
    missing_rows:     int
    preview_snapshot: Optional[dict] = None
    lines:            List[BatchLineIn] = []

class BatchApproveIn(BaseModel):
    journal_entry_id: str


# ─── helpers ──────────────────────────────────────────────────────────────────

def _period_str(month: int, year: int) -> str:
    return f"{year}-{month:02d}"


# ─── GET /import-batches ──────────────────────────────────────────────────────

@router.get("")
async def list_batches(municipality_id: str, template_id: Optional[str] = None,
                       limit: int = 50):
    filters = ["b.municipality_id = :muni", "b.is_active = TRUE"]
    values  = {"muni": municipality_id, "limit": limit}
    if template_id:
        filters.append("b.template_id = :tmpl")
        values["tmpl"] = template_id
    where = " AND ".join(filters)
    rows = await database.fetch_all(
        f"""SELECT b.*, t.name AS template_name
            FROM import_batches b JOIN templates t ON t.id = b.template_id
            WHERE {where} ORDER BY b.uploaded_at DESC LIMIT :limit""",
        values=values)
    return rows


# ─── POST /import-batches ─────────────────────────────────────────────────────

@router.post("", status_code=201)
async def create_batch(payload: BatchCreateIn):
    """
    יוצר batch חדש בסטטוס preview_ready.
    בודק כפילות תקופה לפני יצירה.
    """
    # בדוק כפילות תקופה
    existing = await database.fetch_one(
        """SELECT id, status FROM import_batches
           WHERE municipality_id = :muni AND template_id = :tmpl
             AND period_year = :year AND period_month = :month
             AND is_active = TRUE
           ORDER BY batch_version DESC LIMIT 1""",
        values={"muni": payload.municipality_id, "tmpl": payload.template_id,
                "year": payload.period_year, "month": payload.period_month}
    )

    if existing and existing["status"] == "approved":
        raise HTTPException(
            status_code=409,
            detail=f"קיים batch מאושר לתקופה {_period_str(payload.period_month, payload.period_year)}. "
                   f"לתיקון יש ליצור batch_version חדש."
        )

    # חשב batch_version
    version = 1
    if existing:
        version_row = await database.fetch_one(
            """SELECT MAX(batch_version) AS v FROM import_batches
               WHERE municipality_id = :muni AND template_id = :tmpl
                 AND period_year = :year AND period_month = :month""",
            values={"muni": payload.municipality_id, "tmpl": payload.template_id,
                    "year": payload.period_year, "month": payload.period_month}
        )
        version = (version_row["v"] or 0) + 1

    batch_id = str(uuid4())

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
                "muni":    payload.municipality_id,
                "tmpl":    payload.template_id,
                "fname":   payload.source_file_name,
                "month":   payload.period_month,
                "year":    payload.period_year,
                "ver":     version,
                "total":   payload.total_amount,
                "rows":    payload.total_rows,
                "matched": payload.matched_rows,
                "missing": payload.missing_rows,
                "preview": json.dumps(payload.preview_snapshot, ensure_ascii=False)
                           if payload.preview_snapshot else None,
            }
        )

        # שמור שורות קליטה
        for i, line in enumerate(payload.lines, 1):
            await database.execute(
                """INSERT INTO import_batch_lines
                   (id, batch_id, source_key_value, source_description,
                    raw_amount, matched, missing_reason,
                    account_code, split_percent, final_amount, raw_payload)
                   VALUES (:id, :bid, :key, :desc,
                           :raw, :matched, :reason,
                           :acct, :pct, :final, :payload)""",
                values={
                    "id":      str(uuid4()),
                    "bid":     batch_id,
                    "key":     line.source_key_value,
                    "desc":    line.source_description,
                    "raw":     line.raw_amount,
                    "matched": line.matched,
                    "reason":  line.missing_reason,
                    "acct":    line.account_code,
                    "pct":     line.split_percent,
                    "final":   line.final_amount,
                    "payload": json.dumps(line.raw_payload, ensure_ascii=False)
                               if line.raw_payload else None,
                }
            )

    return {
        "id":            batch_id,
        "status":        "preview_ready",
        "batch_version": version,
        "period":        _period_str(payload.period_month, payload.period_year),
        "lines_count":   len(payload.lines),
    }


# ─── POST /import-batches/{id}/approve ───────────────────────────────────────

@router.post("/{batch_id}/approve")
async def approve_batch(batch_id: str, payload: BatchApproveIn):
    """
    Idempotent approve:
    - אם כבר approved → מחזיר journal_entry_id הקיים
    - אם preview_ready → מאשר ומקשר לפקודה
    - אחרת → שגיאה
    """
    batch = await database.fetch_one(
        "SELECT * FROM import_batches WHERE id = :id",
        values={"id": batch_id}
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Batch לא נמצא")

    # idempotent – כבר אושר
    if batch["status"] == "approved":
        return {
            "id":              batch_id,
            "status":          "approved",
            "journal_entry_id": batch["journal_entry_id"],
            "already_approved": True,
        }

    if batch["status"] != "preview_ready":
        raise HTTPException(
            status_code=400,
            detail=f"לא ניתן לאשר batch בסטטוס {batch['status']}"
        )

    # עדכן batch → approved + קישור לפקודה
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    await database.execute(
        """UPDATE import_batches
           SET status = 'approved',
               journal_entry_id = :jid,
               approved_at = :now,
               updated_at = :now
           WHERE id = :id AND status = 'preview_ready'""",
        values={"id": batch_id, "jid": payload.journal_entry_id, "now": now}
    )

    # עדכן journal_entry עם source_batch_id
    period = f"{batch['period_year']}-{batch['period_month']:02d}"
    await database.execute(
        """UPDATE journal_entries
           SET source_batch_id     = :bid,
               source_type         = 'import_batch',
               source_period_month = :month,
               source_period_year  = :year
           WHERE id = :jid""",
        values={
            "bid":   batch_id,
            "month": batch["period_month"],
            "year":  batch["period_year"],
            "jid":   payload.journal_entry_id,
        }
    )

    return {
        "id":              batch_id,
        "status":          "approved",
        "journal_entry_id": payload.journal_entry_id,
        "already_approved": False,
    }


# ─── POST /import-batches/{id}/cancel ────────────────────────────────────────

@router.post("/{batch_id}/cancel")
async def cancel_batch(batch_id: str, reason: Optional[str] = None):
    batch = await database.fetch_one(
        "SELECT id, status FROM import_batches WHERE id = :id",
        values={"id": batch_id}
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Batch לא נמצא")
    if batch["status"] == "approved":
        raise HTTPException(status_code=400, detail="לא ניתן לבטל batch מאושר")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    await database.execute(
        """UPDATE import_batches
           SET status = 'cancelled', is_active = FALSE,
               cancelled_at = :now, cancel_reason = :reason, updated_at = :now
           WHERE id = :id""",
        values={"id": batch_id, "now": now, "reason": reason}
    )
    return {"cancelled": True}


# ─── GET /import-batches/{id}/lines ──────────────────────────────────────────

@router.get("/{batch_id}/lines")
async def get_batch_lines(batch_id: str, matched: Optional[bool] = None):
    filters = ["batch_id = :bid"]
    values  = {"bid": batch_id}
    if matched is not None:
        filters.append("matched = :matched")
        values["matched"] = matched
    where = " AND ".join(filters)
    rows = await database.fetch_all(
        f"SELECT * FROM import_batch_lines WHERE {where} ORDER BY created_at",
        values=values
    )
    return rows
