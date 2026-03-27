# routers/template_rules.py – ניהול כללי ולידציה לפי תבנית
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
import db; database = db

router = APIRouter()


class RuleUpsert(BaseModel):
    rule_key:   str
    rule_value: str
    description: Optional[str] = None


@router.get("")
async def list_rules(template_id: str):
    """כל הכללים לתבנית מסוימת"""
    rows = await database.fetch_all(
        "SELECT * FROM template_rules WHERE template_id = :tmpl ORDER BY rule_key",
        values={"tmpl": template_id}
    )
    return rows


@router.get("/by-name/{template_name}")
async def get_rules_by_name(template_name: str):
    """כללים לפי שם תבנית (electricity / bezeq)"""
    rows = await database.fetch_all(
        """SELECT r.* FROM template_rules r
           JOIN templates t ON t.id = r.template_id
           WHERE t.name = :name ORDER BY r.rule_key""",
        values={"name": template_name}
    )
    # המר לdict נוח
    return {r["rule_key"]: r["rule_value"] for r in rows}


@router.put("/{template_id}")
async def upsert_rule(template_id: str, payload: RuleUpsert):
    """הוסף או עדכן כלל"""
    existing = await database.fetch_one(
        "SELECT id FROM template_rules WHERE template_id = :tmpl AND rule_key = :key",
        values={"tmpl": template_id, "key": payload.rule_key}
    )
    if existing:
        await database.execute(
            "UPDATE template_rules SET rule_value = :val, description = :desc WHERE id = :id",
            values={"id": existing["id"], "val": payload.rule_value, "desc": payload.description}
        )
        return {"updated": True, "id": existing["id"]}
    else:
        rule_id = str(uuid4())
        await database.execute(
            """INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
               VALUES (:id, :tmpl, :key, :val, :desc)""",
            values={"id": rule_id, "tmpl": template_id, "key": payload.rule_key,
                    "val": payload.rule_value, "desc": payload.description}
        )
        return {"created": True, "id": rule_id}
