# routers/export_events.py – היסטוריית יצוא
import hashlib, io
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from uuid import uuid4
from datetime import datetime, timezone
import db; database = db

router = APIRouter()


@router.get("")
async def list_export_events(journal_entry_id: str):
    rows = await database.fetch_all(
        """SELECT * FROM export_events
           WHERE journal_entry_id = :jid
           ORDER BY exported_at DESC""",
        values={"jid": journal_entry_id}
    )
    return rows


@router.get("/by-municipality")
async def list_by_municipality(municipality_id: str, limit: int = 50):
    rows = await database.fetch_all(
        """SELECT e.*, je.reference_num, je.period
           FROM export_events e
           JOIN journal_entries je ON je.id = e.journal_entry_id
           WHERE e.municipality_id = :muni
           ORDER BY e.exported_at DESC LIMIT :limit""",
        values={"muni": municipality_id, "limit": limit}
    )
    return rows
