# routers/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import db; database = db
import hashlib, secrets

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

@router.post("/login")
async def login(payload: LoginRequest):
    user = await database.fetch_one(
        "SELECT id, name, email, role FROM users WHERE email = :email AND password_hash = :pw AND active = TRUE",
        values={"email": payload.email, "pw": hash_password(payload.password)})
    if not user:
        raise HTTPException(status_code=401, detail="אימייל או סיסמה שגויים")
    munis = await database.fetch_all(
        """SELECT m.id, m.name, m.code FROM municipalities m
           JOIN user_municipality um ON um.municipality_id = m.id
           WHERE um.user_id = :uid AND m.active = TRUE""",
        values={"uid": user["id"]})
    token = secrets.token_hex(32)  # Replace with JWT in production
    return {
        "token": token,
        "user":  dict(user),
        "municipalities": [dict(m) for m in munis],
    }
