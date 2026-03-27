"""
migration_sprint3.py – ספרינט 3 יומנית
יוצר:
  - template_rules – ולידציה לפי תבנית
  - reconciliation statuses ב-journal_entries
  - batch versioning improvements
"""
import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://yomanit:secret@localhost:5432/yomanit")

MIGRATIONS = [

# ─── 1. template_rules – ולידציה וקונפיגורציה לפי תבנית ─────────────────────
"""
CREATE TABLE IF NOT EXISTS template_rules (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id     UUID    NOT NULL REFERENCES templates(id),
    rule_key        TEXT    NOT NULL,
    rule_value      TEXT    NOT NULL,
    description     TEXT,
    UNIQUE (template_id, rule_key)
)
""",

# ─── 2. הכנס כללים לחשמל ─────────────────────────────────────────────────────
"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'required_columns',
       'חשבון חוזה בן,סכום כולל מע"מ,כתובת אספקה',
       'עמודות חובה בקובץ חשמל'
FROM templates t WHERE t.name = 'electricity'
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'encoding_order',
       'cp1255,utf-8-sig,iso-8859-8',
       'סדר ניסיון encoding לקובץ חשמל'
FROM templates t WHERE t.name = 'electricity'
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'balance_tolerance',
       '1.00',
       'סבלנות הפרש איזון בשקלים'
FROM templates t WHERE t.name = 'electricity'
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'allow_negative_amounts',
       'true',
       'האם לאפשר סכומים שליליים (זיכויים)'
FROM templates t WHERE t.name = 'electricity'
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'wrong_format_hints',
       'מספר טלפון:נראה כקובץ בזק,מספר מנוי:נראה כקובץ בזק',
       'רמזים לפורמט שגוי ומסרי שגיאה'
FROM templates t WHERE t.name = 'electricity'
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

# ─── 3. כללים לבזק ───────────────────────────────────────────────────────────
"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'required_columns',
       'מספר טלפון,סכום לתשלום',
       'עמודות חובה בקובץ בזק'
FROM templates t WHERE t.name = 'bezeq'
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'balance_tolerance',
       '1.00',
       'סבלנות הפרש איזון בשקלים'
FROM templates t WHERE t.name = 'bezeq'
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'allow_negative_amounts',
       'false',
       'בזק לא מאפשר זיכויים שליליים'
FROM templates t WHERE t.name = 'bezeq'
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

# ─── 4. reconciliation statuses ב-journal_entries ────────────────────────────
"""
ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS integration_status TEXT
        DEFAULT 'pending'
        CHECK (integration_status IN ('pending','exported','imported_to_ledger','reconciled','error')),
    ADD COLUMN IF NOT EXISTS reconciled_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reconciled_by      TEXT,
    ADD COLUMN IF NOT EXISTS reconcile_notes    TEXT
""",

# ─── 5. batch replacement – עמודת replaces_batch_id כבר קיימת מספרינט 1 ─────
# רק מוסיפים אינדקס על is_active + period
"""
CREATE INDEX IF NOT EXISTS idx_import_batches_active_period
ON import_batches (municipality_id, template_id, period_year, period_month)
WHERE is_active = TRUE AND status = 'approved'
""",

# ─── 6. decimal_policy – policy עיגול אחיד ───────────────────────────────────
"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'decimal_places',
       '2',
       'מספר ספרות אחרי נקודה עשרונית'
FROM templates t WHERE t.name IN ('electricity', 'bezeq')
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

"""
INSERT INTO template_rules (id, template_id, rule_key, rule_value, description)
SELECT gen_random_uuid(), t.id, 'rounding_mode',
       'ROUND_HALF_UP',
       'מצב עיגול – שורת שארית על האחרון'
FROM templates t WHERE t.name IN ('electricity', 'bezeq')
ON CONFLICT (template_id, rule_key) DO NOTHING
""",

]


async def run():
    print("Connecting to DB...")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        for i, sql in enumerate(MIGRATIONS, 1):
            sql = sql.strip()
            if not sql or sql.startswith('--'):
                continue
            print(f"[{i}/{len(MIGRATIONS)}] Running: {sql[:60]}...")
            await conn.execute(sql)
            print(f"  ✓ Done")

        print("\n✅ Sprint 3 migration complete!")
        print("Created/updated:")
        print("  - template_rules (electricity + bezeq rules)")
        print("  - journal_entries (integration_status, reconciled_at)")
        print("  - import_batches (active period index)")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
