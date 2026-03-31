# index_cache.py – מטמון מרכזי לאינדקסים
# מבטיח קריאה אחת ל-DB לכל municipality+template (לא לפי request)
# נרמול semel: חד-כיווני 7→6 בלבד, אף פעם לא 6→7
import asyncio
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

_cache: Dict[Tuple[str, str], dict] = {}
_lock = asyncio.Lock()


def _semel_variants(raw) -> list:
    """
    מייצר variants בטוחים בלבד — חד-כיווני 7→6.
    DB: 1038100 (7 ספרות) → ['1038100', '038100']
    DB: 242410  (6 ספרות) → ['242410']
    כלל: רק הקטנה, לא הרחבה — מונע false matches עתידיים.
    """
    if raw is None:
        return []
    s = str(raw).strip()
    if s.endswith('.0'):
        s = s[:-2]
    s = ''.join(c for c in s if c.isdigit())
    if not s:
        return []
    variants = [s]
    # אם 7 ספרות ומתחיל ב-1 → גרסה מקוצרת ללא ה-1
    if len(s) == 7 and s.startswith('1'):
        variants.append(s[1:])
    return variants


async def get_index(municipality_id: str, template_id: str, db) -> dict:
    """מחזיר index_map ממטמון. אם חסר — טוען מ-DB פעם אחת בלבד."""
    key = (str(municipality_id), str(template_id))
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
            raw_semel = row["key_value"]
            acct      = row["account_code"]
            side      = row["description"]

            if side not in ("debit", "credit"):
                continue

            variants = _semel_variants(raw_semel)
            if not variants:
                logger.warning(f"[INDEX_CACHE] invalid key_value skipped: {raw_semel!r}")
                continue

            for semel in variants:
                if semel not in index_map:
                    index_map[semel] = {}

                # בדיקת conflict — אזהרה אם אותו צד נדרס בערך שונה
                if side in index_map[semel] and index_map[semel][side] != acct:
                    logger.warning(
                        f"[INDEX_CACHE] conflict semel={semel} side={side}: "
                        f"{index_map[semel][side]} → {acct} (DB key={raw_semel})"
                    )

                index_map[semel][side] = acct

                # trace כשמשתמשים ב-variant מקוצר
                if semel != variants[0]:
                    logger.debug(
                        f"[INDEX_CACHE] variant: {variants[0]} → {semel}"
                    )

        # בדיקת שלמות mapping — semel ללא שני הצדדים
        for semel, sides in index_map.items():
            if "debit" not in sides or "credit" not in sides:
                logger.warning(
                    f"[INDEX_CACHE] incomplete mapping semel={semel} "
                    f"sides={list(sides.keys())}"
                )

        logger.info(
            f"[INDEX_CACHE] loaded {len(index_map)} entries "
            f"for municipality={str(municipality_id)[:8]}..."
        )
        _cache[key] = index_map
        return index_map


def invalidate(municipality_id: str, template_id: str) -> None:
    """מנקה cache לאחר עדכון אינדקס."""
    _cache.pop((str(municipality_id), str(template_id)), None)
    logger.debug(f"[INDEX_CACHE] invalidated {str(municipality_id)[:8]}...")


def clear_all() -> None:
    """מנקה את כל ה-cache (לטסטים)."""
    _cache.clear()
    logger.debug("[INDEX_CACHE] cleared all")
