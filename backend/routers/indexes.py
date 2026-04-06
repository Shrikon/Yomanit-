# routers/indexes.py – ניהול אינדקסים עם תמיכה בפיצול אחוזים

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from decimal import Decimal
import pandas as pd, io
import db; database = db

router = APIRouter()

class IndexCreate(BaseModel):
    municipality_id: str
    template_id:     str
    key_value:       str
    account_code:    str
    description:     Optional[str] = None
    connection_name: Optional[str] = None

class IndexBulk(BaseModel):
    municipality_id: str
    template_id:     str
    items: List[IndexCreate]

class SplitRow(BaseModel):
    account_code: str
    percent:      Decimal  # חייב להיות > 0

class SplitUpdate(BaseModel):
    municipality_id: str
    template_id:     str
    key_value:       str
    connection_name: Optional[str] = None
    splits:          List[SplitRow]  # רשימת פיצולים – חייב לסכם ל-100


def validate_splits(splits: List[SplitRow], key_value: str):
    """ולידציה של פיצול אחוזים – זורק HTTPException אם לא תקין"""
    if not splits:
        raise HTTPException(status_code=400, detail=f"חוזה {key_value}: חייב לפחות פיצול אחד")

    for s in splits:
        if s.percent <= 0:
            raise HTTPException(status_code=400, detail=f"חוזה {key_value}: אחוז שלילי או אפס אסור")
        if not s.account_code.strip():
            raise HTTPException(status_code=400, detail=f"חוזה {key_value}: קוד חשבון ריק")

    total = sum(s.percent for s in splits)
    if total != Decimal("100"):
        raise HTTPException(status_code=400,
            detail=f"חוזה {key_value}: סכום האחוזים = {total}, חייב להיות 100 בדיוק")

    accounts = [s.account_code.strip() for s in splits]
    if len(accounts) != len(set(accounts)):
        raise HTTPException(status_code=400,
            detail=f"חוזה {key_value}: כפילות קודי חשבון")


# GET /indexes – חיפוש אינדקסים
@router.get("")
async def list_indexes(municipality_id: str, template_id: Optional[str] = None,
                       search: Optional[str] = None, limit: int = 200):
    filters = ["i.municipality_id = :muni", "i.active = TRUE"]
    values  = {"muni": municipality_id, "limit": limit}
    if template_id:
        filters.append("i.template_id = :tmpl")
        values["tmpl"] = template_id
    if search:
        filters.append("(i.key_value ILIKE :q OR i.connection_name ILIKE :q OR i.account_code ILIKE :q)")
        values["q"] = f"%{search}%"
    where = " AND ".join(filters)
    rows = await database.fetch_all(
        f"""
        SELECT i.*, t.name AS template_name, t.display_name
        FROM   indexes i JOIN templates t ON t.id = i.template_id
        WHERE  {where} ORDER BY i.key_value, i.description LIMIT :limit
        """, values=values)
    return [dict(r) for r in rows]


# POST /indexes – הוספת אינדקס בודד (100%)
@router.post("", status_code=201)
async def create_index(payload: IndexCreate):
    idx_id = str(uuid4())
    desc = payload.description or "100"
    try:
        await database.execute(
            """
            INSERT INTO indexes (id, municipality_id, template_id, key_value, account_code, description, connection_name)
            VALUES (:id, :muni, :tmpl, :key, :acct, :desc, :conn)
            ON CONFLICT (municipality_id, template_id, key_value, account_code)
            DO UPDATE SET description     = EXCLUDED.description,
                          connection_name = EXCLUDED.connection_name,
                          updated_at      = NOW()
            """,
            values={"id": idx_id, "muni": payload.municipality_id, "tmpl": payload.template_id,
                    "key": payload.key_value, "acct": payload.account_code,
                    "desc": desc, "conn": payload.connection_name})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    from index_cache import invalidate
    invalidate(payload.municipality_id, payload.template_id)
    return {"id": idx_id, "created": True}


# PUT /indexes/split – שמירת פיצול מלא לחוזה
@router.put("/split", status_code=200)
async def upsert_split(payload: SplitUpdate):
    validate_splits(payload.splits, payload.key_value)

    async with database.transaction():
        await database.execute(
            """UPDATE indexes SET active = FALSE
               WHERE municipality_id = :muni AND template_id = :tmpl AND key_value = :key""",
            values={"muni": payload.municipality_id, "tmpl": payload.template_id,
                    "key": payload.key_value})

        for split in payload.splits:
            await database.execute(
                """
                INSERT INTO indexes (id, municipality_id, template_id, key_value, account_code, description, connection_name)
                VALUES (:id, :muni, :tmpl, :key, :acct, :desc, :conn)
                ON CONFLICT (municipality_id, template_id, key_value, account_code)
                DO UPDATE SET description     = EXCLUDED.description,
                              connection_name = EXCLUDED.connection_name,
                              active          = TRUE,
                              updated_at      = NOW()
                """,
                values={"id": str(uuid4()), "muni": payload.municipality_id,
                        "tmpl": payload.template_id, "key": payload.key_value,
                        "acct": split.account_code.strip(),
                        "desc": str(split.percent),
                        "conn": payload.connection_name})

    return {"updated": True, "splits": len(payload.splits)}


# POST /indexes/bulk – ייבוא מרובה (קליטה ראשונית)
@router.post("/bulk", status_code=201)
async def create_indexes_bulk(payload: IndexBulk):
    created = 0
    for item in payload.items:
        desc = item.description or "100"
        await database.execute(
            """
            INSERT INTO indexes (id, municipality_id, template_id, key_value, account_code, description, connection_name)
            VALUES (:id, :muni, :tmpl, :key, :acct, :desc, :conn)
            ON CONFLICT (municipality_id, template_id, key_value, account_code)
            DO UPDATE SET description = EXCLUDED.description, updated_at = NOW()
            """,
            values={"id": str(uuid4()), "muni": payload.municipality_id,
                    "tmpl": payload.template_id, "key": item.key_value,
                    "acct": item.account_code, "desc": desc,
                    "conn": item.connection_name})
        created += 1
    return {"created": created}


# POST /indexes/import – ייבוא מ-Excel
@router.post("/import")
async def import_indexes(
    file: UploadFile = File(...),
    municipality_id: str = Form(...),
    template_id:     str = Form(...),
):
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content)) if file.filename.endswith((".xlsx",".xls")) \
             else pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"שגיאת קריאה: {e}")

    created, errors = 0, []
    for _, row in df.iterrows():
        key  = str(row.get("key_value") or row.get("phone") or row.get("טלפון") or "").strip()
        acct = str(row.get("account_code") or row.get("account") or row.get("חשבון") or "").strip()
        desc = str(row.get("description") or row.get("תיאור") or "100").strip()
        conn = str(row.get("connection_name") or row.get("שם_חיבור") or "").strip() or None
        if not key or not acct:
            errors.append(f"שורה חסרה: {dict(row)}")
            continue
        await database.execute(
            """
            INSERT INTO indexes (id, municipality_id, template_id, key_value, account_code, description, connection_name)
            VALUES (:id, :muni, :tmpl, :key, :acct, :desc, :conn)
            ON CONFLICT (municipality_id, template_id, key_value, account_code)
            DO UPDATE SET description = EXCLUDED.description, updated_at = NOW()
            """,
            values={"id": str(uuid4()), "muni": municipality_id, "tmpl": template_id,
                    "key": key, "acct": acct, "desc": desc, "conn": conn})
        created += 1
    return {"created": created, "errors": errors}


# PATCH /indexes/{id} – עדכון שדה בודד
@router.patch("/{index_id}")
async def update_index(index_id: str, payload: dict):
    fields = []
    values = {"id": index_id}
    if "account_code" in payload:
        fields.append("account_code = :acct")
        values["acct"] = payload["account_code"]
    if "connection_name" in payload:
        fields.append("connection_name = :conn")
        values["conn"] = payload["connection_name"]
    if "description" in payload:
        fields.append("description = :desc")
        values["desc"] = str(payload["description"])
    if not fields:
        return {"updated": False}
    row = await database.fetch_one("SELECT municipality_id, template_id, account_code FROM indexes WHERE id = :id", values={"id": index_id})
    try:
        await database.execute(
            f"UPDATE indexes SET {', '.join(fields)}, updated_at = NOW() WHERE id = :id",
            values=values)
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            # PENDING row conflicts with existing real row — delete the pending one
            if row and (str(row["account_code"] or "")).startswith("PENDING"):
                await database.execute("DELETE FROM indexes WHERE id = :id", values={"id": index_id})
                if row:
                    from index_cache import invalidate
                    invalidate(str(row["municipality_id"]), str(row["template_id"]))
                return {"updated": True, "merged": True}
            raise HTTPException(status_code=409, detail=f"סעיף חשבון זה כבר קיים באינדקס")
        raise
    if row:
        from index_cache import invalidate
        invalidate(str(row["municipality_id"]), str(row["template_id"]))
    return {"updated": True}


# DELETE /indexes/{id}
@router.delete("/{index_id}")
async def delete_index(index_id: str):
    row = await database.fetch_one("SELECT municipality_id, template_id FROM indexes WHERE id = :id", values={"id": index_id})
    await database.execute(
        "UPDATE indexes SET active = FALSE WHERE id = :id", values={"id": index_id})
    if row:
        from index_cache import invalidate
        invalidate(str(row["municipality_id"]), str(row["template_id"]))
    return {"deleted": True}
