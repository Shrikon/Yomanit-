# routers/celcom.py – מודול סלקום
# preview מתוקן לפי ביקורת מלאה – גרסה סופית לביקורת

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from uuid import uuid4
from decimal import Decimal, ROUND_HALF_UP
import re, os

router = APIRouter()

def get_db():
    import db
    return db

CELLCOM_VENDOR = "300000"
VAT_INPUT      = "120000"
DEFAULT_BUDGET = "9999"
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads", "celcom")


def normalize_phone(phone) -> str:
    """נרמול עמיד – regex מסיר כל תו שאינו ספרה"""
    if phone is None:
        return ""
    s = str(phone).strip()
    if s.lower() in ("nan", "none", "", "0"):
        return ""
    s = re.sub(r'\D', '', s)
    if not s:
        return ""
    if s.startswith("972"):
        s = s[3:]
        if not s.startswith("0"):
            s = "0" + s
    s = s.lstrip("0")
    return s if s.isdigit() and s else ""


def _r2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fmt(d: Decimal) -> str:
    """המרה ל-JSON ללא float – str עם 2 ספרות עשרוניות"""
    return format(d, '.2f')


# ─────────────────────────────────────────────────────────────────────────────
# CRUD אינדקס
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/index")
async def list_index(municipality_id: str):
    rows = await get_db().fetch_all(
        """SELECT id, phone_number, budget_section, created_at, updated_at
           FROM celcom_index WHERE municipality_id = :muni ORDER BY phone_number""",
        values={"muni": municipality_id},
    )
    return [dict(r) for r in rows]


@router.post("/index", status_code=201)
async def upsert_index(
    municipality_id: str = Form(...),
    phone_number:    str = Form(...),
    budget_section:  str = Form(...),
):
    phone = normalize_phone(phone_number)
    if not phone or not budget_section:
        raise HTTPException(status_code=422, detail="חסרים שדות חובה")
    await get_db().execute(
        """INSERT INTO celcom_index (id, municipality_id, phone_number, budget_section)
           VALUES (:id, :muni, :phone, :section)
           ON CONFLICT (municipality_id, phone_number)
           DO UPDATE SET budget_section = EXCLUDED.budget_section, updated_at = NOW()""",
        values={"id": str(uuid4()), "muni": municipality_id, "phone": phone, "section": budget_section},
    )
    return {"ok": True, "phone_number": phone, "budget_section": budget_section}


@router.delete("/index/{record_id}")
async def delete_index(record_id: str):
    existing = await get_db().fetch_one("SELECT id FROM celcom_index WHERE id = :id", values={"id": record_id})
    if not existing:
        raise HTTPException(status_code=404, detail="רשומה לא נמצאה")
    await get_db().execute("DELETE FROM celcom_index WHERE id = :id", values={"id": record_id})
    return {"deleted": True}


# ─────────────────────────────────────────────────────────────────────────────
# POST /celcom/preview
#
# לוגיקה:
# 1. parse  → rows טהורים (Decimal, ללא float)
# 2. group  → by phone (סכום כל רכיבי המנוי)
# 3. verify → sum(grouped) == sum(original rows)  ← בדיקת שלמות
# 4. index  → load once, O(1) lookup
# 5. split  → mapped / missing
# 6. verify → diff = H_TOTAL – sum_grouped <= 0.10
# 7. return → מבנה אחיד, ממוין, ללא float בחישובים
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/preview")
async def preview_celcom(
    file:            UploadFile = File(...),
    municipality_id: str        = Form(...),
):
    from parsers.celcom import parse_celcom, CelcomParserError

    filename = file.filename or ""
    if not filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="נדרש קובץ Excel (xlsx/xls)")

    content = await file.read()

    # ── 1. Parser ──────────────────────────────────────────────────────────
    try:
        parsed = parse_celcom(content)
    except CelcomParserError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בעיבוד הקובץ: {e}")

    # ── 2. אינדקס – טעינה אחת, O(1) ──────────────────────────────────────
    index_rows = await get_db().fetch_all(
        "SELECT phone_number, budget_section FROM celcom_index WHERE municipality_id = :muni",
        values={"muni": municipality_id},
    )
    index_map: dict[str, str] = {
        normalize_phone(r["phone_number"]): r["budget_section"]
        for r in index_rows
    }

    # ── 3. Group by phone + סינון ─────────────────────────────────────────
    # כל הרכיבים (CE*1.18 + CF + CG) כבר מחוברים ל-amount ב-parser
    # group מוודא שמנוי שמופיע כמה פעמים מקובץ נכון
    grouped: dict[str, dict] = {}  # phone → {amount, name, source, raw_rows}

    sum_original = Decimal("0")  # לבדיקת שלמות

    for sub in parsed["rows"]:
        phone = normalize_phone(sub["phone"])
        if not phone:
            continue
        amount = sub["amount"]  # Decimal
        if amount == Decimal("0"):
            continue

        sum_original = _r2(sum_original + amount)

        if phone not in grouped:
            grouped[phone] = {
                "phone":     phone,
                "name":      sub.get("name", ""),
                "amount":    Decimal("0"),
                "source":    sub.get("source", ""),
                "raw_count": 0,
            }
        grouped[phone]["amount"]    = _r2(grouped[phone]["amount"] + amount)
        grouped[phone]["raw_count"] += 1

    # ── 4. בדיקת שלמות: sum(grouped) == sum(original rows) ───────────────
    sum_grouped = _r2(sum(d["amount"] for d in grouped.values()))
    if sum_grouped != sum_original:
        raise HTTPException(
            status_code=500,
            detail=f"שגיאת grouping פנימית: sum_original={sum_original} ≠ sum_grouped={sum_grouped}"
        )

    # ── 5. Apply index → mapped / missing ─────────────────────────────────
    mapped_list:   list[dict] = []
    missing_list:  list[dict] = []

    for phone, data in grouped.items():
        amount = data["amount"]
        if amount == Decimal("0"):
            continue

        budget = index_map.get(phone, DEFAULT_BUDGET)
        is_mapped = phone in index_map

        entry = {
            "phone":     phone,
            "name":      data["name"],
            "amount":    _fmt(amount),   # str, לא float
            "budget":    budget,
            "mapped":    is_mapped,
            "source":    data["source"],
            "raw_count": data["raw_count"],
        }

        if is_mapped:
            mapped_list.append(entry)
        else:
            missing_list.append(entry)

    # ── 6. סיכומים – הכל Decimal ──────────────────────────────────────────
    invoice_total  = parsed["H_TOTAL"]                  # Decimal
    mapped_total   = _r2(sum(Decimal(s["amount"]) for s in mapped_list))
    unmapped_total = _r2(sum(Decimal(s["amount"]) for s in missing_list))
    diff           = _r2(invoice_total - sum_grouped)
    balance_ok     = abs(diff) <= Decimal("0.10")

    # ── 7. מיון דטרמיניסטי ────────────────────────────────────────────────
    all_subscribers = sorted(mapped_list + missing_list, key=lambda x: x["phone"])

    return {
        "file_type": parsed["file_type"],
        "invoice": {
            "date":   parsed["inv_date"],
            "number": parsed["inv_num"],
            "total":  _fmt(invoice_total),
            "vat":    _fmt(parsed["H12"]),
            "exempt": _fmt(parsed["H13"]),
            "equip":  _fmt(parsed["H14"]),
        },
        "subscribers":     all_subscribers,
        "unmapped":        missing_list,
        "balance_ok":      balance_ok,
        "balance_warning": None if balance_ok else f"הפרש חריג: ₪{_fmt(diff)}",
        "summary": {
            "total_subscribers": len(all_subscribers),
            "mapped_count":      len(mapped_list),
            "unmapped_count":    len(missing_list),
            "mapped_total":      _fmt(mapped_total),
            "unmapped_total":    _fmt(unmapped_total),
            "sum_subscribers":   _fmt(sum_grouped),
            "invoice_total":     _fmt(invoice_total),
            "diff":              _fmt(diff),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /celcom/approve – ממתין לביקורת transaction לפני הפעלה
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/approve", status_code=201)
async def approve_celcom(
    file:            UploadFile = File(...),
    municipality_id: str        = Form(...),
    period:          str        = Form(...),
):
    from parsers.celcom import parse_celcom, CelcomParserError

    filename = file.filename or ""
    content  = await file.read()

    try:
        parsed = parse_celcom(content)
    except CelcomParserError as e:
        raise HTTPException(status_code=422, detail=str(e))

    index_rows = await get_db().fetch_all(
        "SELECT phone_number, budget_section FROM celcom_index WHERE municipality_id = :muni",
        values={"muni": municipality_id},
    )
    index_map: dict[str, str] = {
        normalize_phone(r["phone_number"]): r["budget_section"]
        for r in index_rows
    }

    # ── Group by phone ─────────────────────────────────────────────────────
    grouped: dict[str, Decimal] = {}
    for sub in parsed["rows"]:
        phone = normalize_phone(sub["phone"])
        if not phone:
            continue
        amount = sub["amount"]
        if amount == Decimal("0"):
            continue
        grouped[phone] = _r2(grouped.get(phone, Decimal("0")) + amount)

    # ── קיבוץ לפי סעיף תקציבי ─────────────────────────────────────────────
    budget_totals: dict[str, Decimal] = {}
    unmapped_records: list[dict] = []

    for phone, amount in grouped.items():
        budget = index_map.get(phone, DEFAULT_BUDGET)
        budget_totals[budget] = _r2(budget_totals.get(budget, Decimal("0")) + amount)
        if phone not in index_map:
            unmapped_records.append({
                "phone": phone, "amount": amount, "file_name": filename
            })

    # ── בדיקת כפילות תקופה ────────────────────────────────────────────────
    tmpl_row = await get_db().fetch_one("SELECT id FROM templates WHERE name = 'cellcom' LIMIT 1")
    if not tmpl_row:
        raise HTTPException(status_code=500, detail="תבנית cellcom לא נמצאה")
    tmpl_id = tmpl_row["id"]

    existing = await get_db().fetch_one(
        """SELECT id, reference_num FROM journal_entries
           WHERE municipality_id = :muni AND template_id = :tmpl AND period = :period""",
        values={"muni": municipality_id, "tmpl": tmpl_id, "period": period},
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"קיימת פקודה לתקופה {period}: {existing['reference_num']}")

    # ── אימות: חובה = זכות לפני כתיבה ────────────────────────────────────
    H_TOTAL    = parsed["H_TOTAL"]
    H12        = parsed["H12"]
    sum_debits = _r2(H12 + sum(budget_totals.values()))

    if abs(sum_debits - H_TOTAL) > Decimal("0.10"):
        raise HTTPException(
            status_code=422,
            detail=f"פקודה לא מאוזנת: חובה={_fmt(sum_debits)} ≠ זכות={_fmt(H_TOTAL)}"
        )

    # ── שמירת קובץ ────────────────────────────────────────────────────────
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id   = str(uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
    with open(file_path, "wb") as f:
        f.write(content)
    await get_db().execute(
        """INSERT INTO uploaded_files (id, municipality_id, file_name, file_path, source_type)
           VALUES (:id, :muni, :name, :path, 'CELLCOM')""",
        values={"id": file_id, "muni": municipality_id, "name": filename, "path": file_path},
    )

    # ── בניית פקודה ───────────────────────────────────────────────────────
    inv_num  = parsed["inv_num"]
    entry_id = str(uuid4())
    ref_num  = f"CLCM-{period.replace('-','')}-{entry_id[:6].upper()}"

    async with get_db().transaction():
        await get_db().execute(
            """INSERT INTO journal_entries
               (id, municipality_id, template_id, period, reference_num,
                source_file, source_file_id, total_amount, status, source_type)
               VALUES (:id,:muni,:tmpl,:period,:ref,:src,:srcid,:total,'draft','CELLCOM')""",
            values={
                "id": entry_id, "muni": municipality_id, "tmpl": tmpl_id,
                "period": period, "ref": ref_num,
                "src": filename, "srcid": file_id,
                "total": float(H_TOTAL),
            }
        )

        line_num = 1

        # זכות – חו"ז סלקום
        await get_db().execute(
            """INSERT INTO journal_lines
               (id, entry_id, line_num, account, description, debit, credit, budget_section)
               VALUES (:id,:entry,:num,:acct,:desc,0,:credit,NULL)""",
            values={
                "id": str(uuid4()), "entry": entry_id, "num": line_num,
                "acct": CELLCOM_VENDOR,
                "desc": f"חו\"ז סלקום חשבונית {inv_num}",
                "credit": float(H_TOTAL),
            }
        )
        line_num += 1

        # חובה – מע"מ תשומות
        if H12 > Decimal("0"):
            await get_db().execute(
                """INSERT INTO journal_lines
                   (id, entry_id, line_num, account, description, debit, credit, budget_section)
                   VALUES (:id,:entry,:num,:acct,:desc,:debit,0,NULL)""",
                values={
                    "id": str(uuid4()), "entry": entry_id, "num": line_num,
                    "acct": VAT_INPUT,
                    "desc": f"מע\"מ תשומות סלקום {period}",
                    "debit": float(H12),
                }
            )
            line_num += 1

        # חובות לפי סעיף – ממוינים, סכום > 0 בלבד
        for budget, amount in sorted(budget_totals.items()):
            rounded = _r2(amount)
            if rounded == Decimal("0"):
                continue
            await get_db().execute(
                """INSERT INTO journal_lines
                   (id, entry_id, line_num, account, description, debit, credit, budget_section)
                   VALUES (:id,:entry,:num,:acct,:desc,:debit,0,:budget)""",
                values={
                    "id": str(uuid4()), "entry": entry_id, "num": line_num,
                    "acct": budget,
                    "desc": f"הוצאות סלקום {period} – סעיף {budget}",
                    "debit": float(rounded),
                    "budget": budget,
                }
            )
            line_num += 1

        # רישום חריגים
        for u in unmapped_records:
            await get_db().execute(
                """INSERT INTO celcom_unmapped (id, municipality_id, phone_number, amount, file_name, entry_id)
                   VALUES (:id,:muni,:phone,:amount,:fname,:entry)""",
                values={
                    "id": str(uuid4()), "muni": municipality_id,
                    "phone": u["phone"], "amount": float(u["amount"]),
                    "fname": filename, "entry": entry_id,
                }
            )

    return {
        "ok":             True,
        "reference_num":  ref_num,
        "entry_id":       entry_id,
        "period":         period,
        "total":          _fmt(H_TOTAL),
        "lines_count":    line_num - 1,
        "budget_lines":   len(budget_totals),
        "unmapped_count": len(unmapped_records),
    }
