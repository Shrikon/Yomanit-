# parsers/electricity_index.py
# טעינת אינדקסי חשמל מה-DB + פיצול תקציב

from typing import Dict, List, Any


async def load_electricity_index(db, municipality_id: str, template_id: str) -> Dict[str, List[Dict]]:
    """
    טוען אינדקסי חשמל מה-DB.

    מחזיר:
    {
        "341838563": [{"account": "1812200431", "percent": 100}],
        "342109870": [
            {"account": "7101017000", "percent": 60},
            {"account": "1938000431", "percent": 40},
        ],
        ...
    }

    שדה key_value = מספר חוזה
    שדה description = אחוז (מספר) או ריק = 100%
    """
    rows = await db.fetch_all(
        """SELECT key_value, account_code, description, connection_name
           FROM   indexes
           WHERE  municipality_id = :muni
             AND  template_id     = :tmpl
             AND  active          = TRUE
           ORDER BY key_value, description""",
        values={"muni": municipality_id, "tmpl": template_id}
    )

    index_map: Dict[str, List[Dict]] = {}

    for row in rows:
        contract = (row["key_value"] or "").strip()
        account  = (row["account_code"] or "").strip()
        if not contract or not account:
            continue

        # אחוז – נשמר בשדה description כמספר (לדוגמה "60" או "100")
        try:
            percent = float(row["description"] or "100")
            if percent <= 0 or percent > 100:
                percent = 100.0
        except (ValueError, TypeError):
            percent = 100.0

        name = (row["connection_name"] or row["description"] or "").strip()

        if contract not in index_map:
            index_map[contract] = []

        index_map[contract].append({
            "account": account,
            "percent": percent,
            "name":    name,
        })

    return index_map


async def lookup_and_split(
    rows: List[Dict],
    db,
    municipality_id: str,
    template_id: str
):
    """
    מבצע index lookup ופיצול תקציב על רשימת שורות.
    מחזיר (matched, missing)
    """
    from parsers.electricity import apply_index_splits

    index_map = await load_electricity_index(db, municipality_id, template_id)
    matched, missing = apply_index_splits(rows, index_map)
    return matched, missing, index_map
