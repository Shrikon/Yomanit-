"""
migration_sprint1.py – ספרינט 1 יומנית
יוצר:
  - import_batches
  - import_batch_lines
  - עמודות חדשות ב-journal_entries
  - שדרוג audit_log
"""
import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://yomanit:secret@localhost:5432/yomanit")

MIGRATIONS = [

# ─── 1. import_batches ───────────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS import_batches (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    municipality_id     UUID        NOT NULL REFERENCES municipalities(id),
    template_id         UUID        NOT NULL REFERENCES templates(id),

    -- קובץ מקור
    source_file_name    TEXT        NOT NULL,
    file_hash           TEXT,               -- SHA-256 למניעת כפילות

    -- תקופה
    period_month        SMALLINT    NOT NULL,  -- 1-12
    period_year         SMALLINT    NOT NULL,  -- 2024, 2025...
    batch_version       SMALLINT    NOT NULL DEFAULT 1,
    replaces_batch_id   UUID        REFERENCES import_batches(id),

    -- lifecycle
    status              TEXT        NOT NULL DEFAULT 'uploaded'
                        CHECK (status IN ('uploaded','parsed','preview_ready','approved','failed','cancelled')),

    -- סטטיסטיקה
    total_amount        NUMERIC(15,2),
    total_rows          INTEGER,
    matched_rows        INTEGER,
    missing_rows        INTEGER,

    -- snapshot של ה-preview שאושר (JSON)
    preview_snapshot    JSONB,

    -- קישור לפקודה שנוצרה
    journal_entry_id    UUID        REFERENCES journal_entries(id),

    -- מעקב
    uploaded_by         TEXT,
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at         TIMESTAMPTZ,
    failed_at           TIMESTAMPTZ,
    failure_reason      TEXT,

    -- soft delete
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    cancelled_at        TIMESTAMPTZ,
    cancelled_by        TEXT,
    cancel_reason       TEXT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""",

# ─── 2. UNIQUE על תקופה (מניעת כפילויות) ─────────────────────────────────────
"""
CREATE UNIQUE INDEX IF NOT EXISTS import_batches_unique_period
ON import_batches (municipality_id, template_id, period_year, period_month, batch_version)
WHERE is_active = TRUE
""",

# ─── 3. import_batch_lines ───────────────────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS import_batch_lines (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID        NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,

    -- נתון מקור
    source_key_value    TEXT        NOT NULL,  -- מספר חוזה / מספר טלפון
    source_description  TEXT,
    raw_amount          NUMERIC(15,2) NOT NULL,

    -- תוצאת matching
    matched             BOOLEAN     NOT NULL DEFAULT FALSE,
    missing_reason      TEXT,

    -- תוצאת פיצול
    account_code        TEXT,
    split_percent       NUMERIC(7,4),          -- 100.0000 / 60.0000 / 40.0000
    final_amount        NUMERIC(15,2),

    -- payload מלא לצורך audit
    raw_payload         JSONB,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
""",

# ─── 4. אינדקסים על import_batch_lines ───────────────────────────────────────
"""
CREATE INDEX IF NOT EXISTS idx_batch_lines_batch_id
ON import_batch_lines (batch_id)
""",

"""
CREATE INDEX IF NOT EXISTS idx_batch_lines_key_value
ON import_batch_lines (source_key_value)
""",

# ─── 5. שדות חדשים ב-journal_entries ─────────────────────────────────────────
"""
ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS source_batch_id    UUID REFERENCES import_batches(id),
    ADD COLUMN IF NOT EXISTS source_type        TEXT,
    ADD COLUMN IF NOT EXISTS source_period_month SMALLINT,
    ADD COLUMN IF NOT EXISTS source_period_year  SMALLINT,
    ADD COLUMN IF NOT EXISTS is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS cancelled_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancelled_by       TEXT,
    ADD COLUMN IF NOT EXISTS cancel_reason      TEXT
""",

# ─── 6. שדרוג audit_log ──────────────────────────────────────────────────────
"""
ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS field_name     TEXT,
    ADD COLUMN IF NOT EXISTS old_value      TEXT,
    ADD COLUMN IF NOT EXISTS new_value      TEXT,
    ADD COLUMN IF NOT EXISTS changed_by     TEXT,
    ADD COLUMN IF NOT EXISTS batch_id       UUID REFERENCES import_batches(id)
""",

# ─── 7. indexes – תוקף תקופתי ────────────────────────────────────────────────
"""
ALTER TABLE indexes
    ADD COLUMN IF NOT EXISTS valid_from     DATE,
    ADD COLUMN IF NOT EXISTS valid_to       DATE
""",

# ─── 8. index_exceptions – תור חוסרים ───────────────────────────────────────
"""
CREATE TABLE IF NOT EXISTS index_exceptions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    municipality_id     UUID        NOT NULL REFERENCES municipalities(id),
    template_id         UUID        NOT NULL REFERENCES templates(id),
    key_value           TEXT        NOT NULL,
    source_description  TEXT,
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    occurrences         INTEGER     NOT NULL DEFAULT 1,
    resolved_at         TIMESTAMPTZ,
    resolved_by         TEXT,
    UNIQUE (municipality_id, template_id, key_value)
)
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

        print("\n✅ Sprint 1 migration complete!")
        print("Tables created/updated:")
        print("  - import_batches")
        print("  - import_batch_lines")
        print("  - journal_entries (new columns)")
        print("  - audit_log (new columns)")
        print("  - indexes (valid_from, valid_to)")
        print("  - index_exceptions")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
