# routers/index_exceptions.py – תור עבודה לחוסרים באינדקס
from fastapi import APIRouter, HTTPException
from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone
import db; database = db

router = APIRouter()


@router.get("")
async def list_exceptions(municipality_id: str, template_id: Optional[str] = None,
                           resolved: bool = False):
    """רשימת חוסרים פתוחים/סגורים"""
    filters = ["municipality_id = :muni"]
    values  = {"muni": municipality_id}
    if template_id:
        filters.append("template_id = :tmpl")
        values["tmpl"] = template_id
    if not resolved:
        filters.append("resolved_at IS NULL")
    else:
        filters.append("resolved_at IS NOT NULL")

    where = " AND ".join(filters)
    rows = await database.fetch_all(
        f"""SELECT e.*, t.name AS template_name
            FROM index_exceptions e JOIN templates t ON t.id = e.template_id
            WHERE {where}
            ORDER BY e.occurrences DESC, e.last_seen_at DESC""",
        values=values
    )
    return rows


@router.post("/upsert")
async def upsert_exception(municipality_id: str, template_id: str,
                            key_value: str, source_description: Optional[str] = None):
    """
    מוסיף חוסר חדש או מעדכן קיים (occurrences++).
    נקרא אוטומטית מ-upload כשיש missing.
    """
    existing = await database.fetch_one(
        """SELECT id, occurrences FROM index_exceptions
           WHERE municipality_id = :muni AND template_id = :tmpl AND key_value = :key""",
        values={"muni": municipality_id, "tmpl": template_id, "key": key_value}
    )

    now = datetime.now(timezone.utc)

    if existing:
        await database.execute(
            """UPDATE index_exceptions
               SET occurrences = occurrences + 1,
                   last_seen_at = :now,
                   source_description = COALESCE(:desc, source_description)
               WHERE id = :id""",
            values={"id": existing["id"], "now": now, "desc": source_description}
        )
        return {"id": existing["id"], "occurrences": existing["occurrences"] + 1}
    else:
        exc_id = str(uuid4())
        await database.execute(
            """INSERT INTO index_exceptions
               (id, municipality_id, template_id, key_value, source_description,
                first_seen_at, last_seen_at, occurrences)
               VALUES (:id, :muni, :tmpl, :key, :desc, :now, :now, 1)""",
            values={"id": exc_id, "muni": municipality_id, "tmpl": template_id,
                    "key": key_value, "desc": source_description, "now": now}
        )
        return {"id": exc_id, "occurrences": 1}


@router.get("/summary")
async def exceptions_summary(municipality_id: str):
    """סיכום חוסרים לפי template"""
    rows = await database.fetch_all(
        """SELECT t.name AS template_name, t.display_name,
                  COUNT(*) AS total,
                  SUM(occurrences) AS total_occurrences
           FROM index_exceptions e JOIN templates t ON t.id = e.template_id
           WHERE e.municipality_id = :muni AND e.resolved_at IS NULL
           GROUP BY t.name, t.display_name""",
        values={"muni": municipality_id}
    )
    return rows


@router.post("/{exception_id}/resolve")
async def resolve_exception(exception_id: str, resolved_by: Optional[str] = None):
    """סימון חוסר כפתור – לאחר הוספת האינדקס"""
    exc = await database.fetch_one(
        "SELECT id FROM index_exceptions WHERE id = :id",
        values={"id": exception_id}
    )
    if not exc:
        raise HTTPException(status_code=404, detail="חוסר לא נמצא")

    await database.execute(
        """UPDATE index_exceptions
           SET resolved_at = :now, resolved_by = :by
           WHERE id = :id""",
        values={"id": exception_id, "now": datetime.now(timezone.utc), "by": resolved_by}
    )
    return {"resolved": True}
