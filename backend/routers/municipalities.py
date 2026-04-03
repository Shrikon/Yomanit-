# routers/municipalities.py
from fastapi import APIRouter
import db; database = db

router = APIRouter()

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


@router.get("/{muni_id}/general-settings")
async def get_general_settings(muni_id: str):
    rows = await database.fetch_all(
        "SELECT key, value FROM municipality_settings WHERE municipality_id = :id AND template_name = 'general'",
        values={"id": muni_id}
    )
    return {r["key"]: r["value"] for r in rows}


@router.post("/{muni_id}/general-settings")
async def save_general_settings(muni_id: str, payload: dict):
    for key, value in payload.items():
        if not key or value is None:
            continue
        await database.execute(
            """INSERT INTO municipality_settings (id, municipality_id, template_name, key, value)
               VALUES (gen_random_uuid(), :muni, 'general', :key, :val)
               ON CONFLICT (municipality_id, template_name, key)
               DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
            values={"muni": muni_id, "key": key, "val": str(value)}
        )
    return {"saved": True}

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
