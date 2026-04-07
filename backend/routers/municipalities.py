# routers/municipalities.py
from fastapi import APIRouter, HTTPException
from uuid import uuid4
import db; database = db

router = APIRouter()

@router.post("", status_code=201)
async def create_municipality(payload: dict):
    name = payload.get("name")
    code = payload.get("code")
    if not name or not code:
        raise HTTPException(status_code=422, detail="name and code required")
    muni_id = str(uuid4())
    await database.execute(
        "INSERT INTO municipalities (id, name, code) VALUES (:id, :name, :code)",
        values={"id": muni_id, "name": name, "code": code}
    )
    return {"id": muni_id, "name": name, "code": code}

@router.get("")
async def list_municipalities():
    rows = await database.fetch_all(
        "SELECT id, name, code FROM municipalities WHERE active = TRUE ORDER BY name")
    return [dict(r) for r in rows]

@router.get("/{muni_id}/stats")
async def municipality_stats(muni_id: str):
    entries = await database.fetch_one(
        "SELECT COUNT(*) as total, SUM(total_amount) as volume FROM journal_entries WHERE municipality_id = :id",
        values={"id": muni_id})
    indexes_count = await database.fetch_one(
        "SELECT COUNT(*) as total FROM indexes WHERE municipality_id = :id AND active = TRUE",
        values={"id": muni_id})
    return {
        "entries":      entries["total"] or 0,
        "volume":       float(entries["volume"] or 0),
        "indexes":      indexes_count["total"] or 0,
    }


@router.delete("/{muni_id}")
async def delete_municipality(muni_id: str):
    """Soft-delete a municipality (set active=FALSE)."""
    await database.execute(
        "UPDATE municipalities SET active = FALSE WHERE id = :id",
        values={"id": muni_id}
    )
    return {"deleted": True}

@router.get("/{muni_id}/settings")
async def get_municipality_settings(muni_id: str):
    rows = await database.fetch_all(
        "SELECT template_name, key, value FROM municipality_settings WHERE municipality_id = :id",
        values={"id": muni_id}
    )
    result = {}
    for r in rows:
        result[r["key"]] = r["value"]
    if "vendor_account" not in result:
        result["vendor_account"] = "6000203000"
    return result

@router.post("/{muni_id}/settings")
async def save_municipality_setting(muni_id: str, payload: dict):
    template_name = payload.get("template_name", "bezeq")
    key   = payload.get("key")
    value = payload.get("value")
    if not key or not value:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="key and value required")
    await database.execute(
        """INSERT INTO municipality_settings (id, municipality_id, template_name, key, value)
           VALUES (gen_random_uuid(), :muni, :tmpl, :key, :val)
           ON CONFLICT (municipality_id, template_name, key)
           DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
        values={"muni": muni_id, "tmpl": template_name, "key": key, "val": value}
    )
    return {"saved": True}
