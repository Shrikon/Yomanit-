# index_cache.py – מטמון מרכזי לאינדקסים
# מבטיח קריאה אחת ל-DB לכל municipality+template (לא לפי request)
import asyncio
from typing import Dict, Tuple

_cache: Dict[Tuple[str, str], dict] = {}
_lock = asyncio.Lock()


async def get_index(municipality_id: str, template_id: str, db) -> dict:
    """מחזיר index_map ממטמון. אם חסר — טוען מ-DB פעם אחת בלבד."""
    key = (municipality_id, template_id)
    if key in _cache:
        return _cache[key]
    async with _lock:
        if key in _cache:
            return _cache[key]
        rows = await db.fetch_all(
            """SELECT key_value, account_code, description
               FROM indexes
               WHERE municipality_id = :muni AND template_id = :tmpl AND active = TRUE""",
            values={"muni": municipality_id, "tmpl": template_id}
        )
        index_map: dict = {}
        for row in rows:
            semel = row["key_value"]
            acct  = row["account_code"]
            side  = row["description"]
            if semel not in index_map:
                index_map[semel] = {}
            if side in ("debit", "credit"):
                index_map[semel][side] = acct
        _cache[key] = index_map
        return index_map


def invalidate(municipality_id: str, template_id: str) -> None:
    """מנקה cache לאחר עדכון אינדקס."""
    _cache.pop((municipality_id, template_id), None)


def clear_all() -> None:
    """מנקה את כל ה-cache (לטסטים)."""
    _cache.clear()
