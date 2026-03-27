"""
migration_sprint2.py – ספרינט 2 יומנית
יוצר:
  - export_events
  - roles + user_roles
  - שדרוג index_exceptions (כבר קיים, מוסיף אינדקסים)
  - שדרוג municipality_settings
"""
import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://yomanit:secret@localhost:5432/yomanit")

MIGRATIONS = [

# ─── 1. export_events – היסטוריית יצוא ──────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS export_events (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_entry_id  UUID        NOT NULL REFERENCES journal_entries(id),
    exported_by       TEXT,
    exported_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    export_format     TEXT        NOT NULL DEFAULT 'xlsx',
    file_name         TEXT,
    checksum          TEXT,
    municipality_id   UUID        REFERENCES municipalities(id)
)
""",

"""
CREATE INDEX IF NOT EXISTS idx_export_events_entry
ON export_events (journal_entry_id)
""",

# ─── 2. roles – טבלת תפקידים ─────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS roles (
    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT    NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB   NOT NULL DEFAULT '[]'
)
""",

"""
INSERT INTO roles (name, description, permissions) VALUES
    ('admin',      'מנהל מערכת – גישה מלאה',
     '["manage_indexes","approve_journal","export_journal","cancel_journal","manage_users","view_all"]'),
    ('accountant', 'חשב – קליטה ואישור פקודות',
     '["manage_indexes","approve_journal","export_journal","view_all"]'),
    ('reviewer',   'מבקר – צפייה בלבד + יצוא',
     '["export_journal","view_all"]'),
    ('readonly',   'קריאה בלבד',
     '["view_all"]')
ON CONFLICT (name) DO NOTHING
""",

# ─── 3. users ─────────────────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT        NOT NULL UNIQUE,
    display_name    TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
)
""",

# ─── 4. user_municipality_roles – הרשאות לפי רשות ───────────────────────────
"""
CREATE TABLE IF NOT EXISTS user_municipality_roles (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id),
    municipality_id UUID        NOT NULL REFERENCES municipalities(id),
    role_id         UUID        NOT NULL REFERENCES roles(id),
    granted_by      TEXT,
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    UNIQUE (user_id, municipality_id)
)
""",

# ─── 5. אינדקסים על index_exceptions ─────────────────────────────────────────
"""
CREATE INDEX IF NOT EXISTS idx_index_exceptions_muni
ON index_exceptions (municipality_id, template_id)
WHERE resolved_at IS NULL
""",

# ─── 6. שדרוג municipality_settings – הוספת שדות שימושיים ───────────────────
"""
ALTER TABLE municipality_settings
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS updated_at  TIMESTAMPTZ DEFAULT NOW()
""",

# ─── 7. הוספת ברירות מחדל לרשויות קיימות ────────────────────────────────────
"""
INSERT INTO municipality_settings (id, municipality_id, template_name, key, value)
SELECT gen_random_uuid(), id, 'electricity', 'rounding_tolerance', '0.10'
FROM municipalities
ON CONFLICT (municipality_id, template_name, key) DO NOTHING
""",

"""
INSERT INTO municipality_settings (id, municipality_id, template_name, key, value)
SELECT gen_random_uuid(), id, 'electricity', 'journal_number_prefix', 'ELEC'
FROM municipalities
ON CONFLICT (municipality_id, template_name, key) DO NOTHING
""",

"""
INSERT INTO municipality_settings (id, municipality_id, template_name, key, value)
SELECT gen_random_uuid(), id, 'bezeq', 'journal_number_prefix', 'BZQ'
FROM municipalities
ON CONFLICT (municipality_id, template_name, key) DO NOTHING
""",

]


async def run():
    print("Connecting to DB...")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        for i, sql in enumerate(MIGRATIONS, 1):
            sql = sql.strip()
            if not sql:
                continue
            print(f"[{i}/{len(MIGRATIONS)}] Running: {sql[:60]}...")
            await conn.execute(sql)
            print(f"  ✓ Done")

        print("\n✅ Sprint 2 migration complete!")
        print("Created/updated:")
        print("  - export_events")
        print("  - roles (admin, accountant, reviewer, readonly)")
        print("  - users")
        print("  - user_municipality_roles")
        print("  - index_exceptions (indexes)")
        print("  - municipality_settings (new columns + defaults)")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
