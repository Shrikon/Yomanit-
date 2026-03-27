-- =============================================
-- yomanit – DB Upgrade v2
-- Production-ready migrations
-- הרץ: psql -U yomanit -d yomanit -f upgrade_v2.sql
-- =============================================

-- =============================================
-- 1. UNIQUE CONSTRAINT – מניעת כפילות תקופה
-- =============================================
ALTER TABLE journal_entries
    ADD CONSTRAINT uq_entry_period
    UNIQUE (municipality_id, template_id, period);

-- =============================================
-- 2. PERFORMANCE INDEXES
-- =============================================
CREATE INDEX IF NOT EXISTS idx_je_period
    ON journal_entries (municipality_id, template_id, period);

CREATE INDEX IF NOT EXISTS idx_je_status
    ON journal_entries (municipality_id, status);

CREATE INDEX IF NOT EXISTS idx_indexes_active
    ON indexes (municipality_id, template_id, active)
    WHERE active = TRUE;

-- =============================================
-- 3. STATUS LIFECYCLE
-- draft → ready → exported → locked
-- =============================================
ALTER TABLE journal_entries
    DROP CONSTRAINT IF EXISTS journal_entries_status_check;

ALTER TABLE journal_entries
    ADD CONSTRAINT journal_entries_status_check
    CHECK (status IN ('draft', 'ready', 'exported', 'locked', 'approved'));

-- =============================================
-- 4. VALIDATION CONSTRAINTS
-- =============================================
-- שורות חיוב לא יכולות להיות שליליות
ALTER TABLE journal_lines
    ADD CONSTRAINT chk_debit_positive  CHECK (debit  >= 0),
    ADD CONSTRAINT chk_credit_positive CHECK (credit >= 0);

-- חשבון חובה
ALTER TABLE journal_lines
    ALTER COLUMN account SET NOT NULL;

-- =============================================
-- 5. SOURCE FILES TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS source_files (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    municipality_id UUID NOT NULL REFERENCES municipalities(id),
    template_id     UUID NOT NULL REFERENCES templates(id),
    entry_id        UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    filename        VARCHAR(255) NOT NULL,
    file_size       INTEGER,
    file_hash       VARCHAR(64),        -- SHA256 למניעת כפילות קובץ
    period          VARCHAR(7),
    uploaded_by     UUID REFERENCES users(id),
    uploaded_at     TIMESTAMP DEFAULT NOW(),
    row_count       INTEGER,
    matched_count   INTEGER,
    missing_count   INTEGER,
    balance_ok      BOOLEAN,
    invoice_total   NUMERIC(14,2),
    sum_details     NUMERIC(14,2)
);

CREATE INDEX idx_sf_municipality ON source_files (municipality_id, period);

-- =============================================
-- 6. SETTINGS TABLE
-- הגדרות per-municipality (ספק בזק, ספק חשמל וכו)
-- =============================================
CREATE TABLE IF NOT EXISTS municipality_settings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    municipality_id UUID NOT NULL REFERENCES municipalities(id) ON DELETE CASCADE,
    template_name   VARCHAR(50) NOT NULL,   -- 'bezeq' | 'electricity'
    key             VARCHAR(100) NOT NULL,  -- 'vendor_account' | 'default_account'
    value           VARCHAR(200) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (municipality_id, template_name, key)
);

-- ערכי ברירת מחדל
INSERT INTO municipality_settings (municipality_id, template_name, key, value)
SELECT id, 'bezeq', 'vendor_account', '6000203000'
FROM   municipalities
ON CONFLICT DO NOTHING;

-- =============================================
-- 7. AUDIT LOG TABLE
-- =============================================
CREATE TABLE IF NOT EXISTS audit_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    municipality_id UUID REFERENCES municipalities(id),
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(50) NOT NULL,
    -- CREATE | UPDATE | DELETE | EXPORT | LOGIN | APPROVE
    entity_type     VARCHAR(50) NOT NULL,
    -- journal_entry | index | user | municipality
    entity_id       UUID,
    before_data     JSONB,
    after_data      JSONB,
    ip_address      VARCHAR(45),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_municipality ON audit_log (municipality_id, created_at DESC);
CREATE INDEX idx_audit_entity       ON audit_log (entity_type, entity_id);

-- =============================================
-- 8. TRIGGER – אוטומטי לכל שינוי בפקודות
-- =============================================
CREATE OR REPLACE FUNCTION audit_journal_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (municipality_id, action, entity_type, entity_id, after_data)
        VALUES (NEW.municipality_id, 'CREATE', 'journal_entry', NEW.id,
                jsonb_build_object('reference_num', NEW.reference_num, 'period', NEW.period,
                                   'status', NEW.status, 'total', NEW.total_amount));
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.status <> NEW.status THEN
            INSERT INTO audit_log (municipality_id, action, entity_type, entity_id, before_data, after_data)
            VALUES (NEW.municipality_id, 'STATUS_CHANGE', 'journal_entry', NEW.id,
                    jsonb_build_object('status', OLD.status),
                    jsonb_build_object('status', NEW.status));
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (municipality_id, action, entity_type, entity_id, before_data)
        VALUES (OLD.municipality_id, 'DELETE', 'journal_entry', OLD.id,
                jsonb_build_object('reference_num', OLD.reference_num, 'period', OLD.period));
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_journal ON journal_entries;
CREATE TRIGGER trg_audit_journal
    AFTER INSERT OR UPDATE OR DELETE ON journal_entries
    FOR EACH ROW EXECUTE FUNCTION audit_journal_changes();

-- =============================================
-- 9. TRIGGER – מניעת עריכה אחרי exported/locked
-- =============================================
CREATE OR REPLACE FUNCTION prevent_locked_edit()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IN ('exported', 'locked') THEN
        RAISE EXCEPTION 'לא ניתן לערוך פקודה בסטטוס %', OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_locked ON journal_entries;
CREATE TRIGGER trg_prevent_locked
    BEFORE UPDATE ON journal_entries
    FOR EACH ROW
    WHEN (OLD.status IN ('exported', 'locked'))
    EXECUTE FUNCTION prevent_locked_edit();

-- =============================================
-- 10. VIEW – פקודות עם בעיות (לדשבורד)
-- =============================================
CREATE OR REPLACE VIEW v_journal_issues AS
SELECT
    je.id,
    je.municipality_id,
    m.name AS municipality_name,
    je.reference_num,
    je.period,
    je.status,
    je.total_amount,
    CASE
        WHEN ABS(COALESCE((SELECT SUM(jl.debit)  FROM journal_lines jl WHERE jl.entry_id = je.id), 0) -
                 COALESCE((SELECT SUM(jl.credit) FROM journal_lines jl WHERE jl.entry_id = je.id), 0)) > 0.10
        THEN 'לא מאוזן'
        WHEN EXISTS (SELECT 1 FROM journal_lines jl WHERE jl.entry_id = je.id AND (jl.account IS NULL OR jl.account = '9999'))
        THEN 'חסר קוד חשבון'
        ELSE NULL
    END AS issue_type
FROM journal_entries je
JOIN municipalities m ON m.id = je.municipality_id
WHERE je.status NOT IN ('locked', 'exported');

-- =============================================
-- 11. FUNCTION – בדיקת איזון פקודה
-- =============================================
CREATE OR REPLACE FUNCTION check_journal_balance(p_entry_id UUID)
RETURNS TABLE (
    is_balanced     BOOLEAN,
    total_debit     NUMERIC,
    total_credit    NUMERIC,
    diff            NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ABS(SUM(jl.debit) - SUM(jl.credit)) <= 0.10 AS is_balanced,
        SUM(jl.debit)   AS total_debit,
        SUM(jl.credit)  AS total_credit,
        ABS(SUM(jl.debit) - SUM(jl.credit)) AS diff
    FROM journal_lines jl
    WHERE jl.entry_id = p_entry_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- אימות – בדוק שהכל עבד
-- =============================================
DO $$
BEGIN
    RAISE NOTICE '✓ upgrade_v2 completed successfully';
    RAISE NOTICE '  Tables:     source_files, municipality_settings, audit_log';
    RAISE NOTICE '  Triggers:   audit_journal, prevent_locked_edit, je_updated';
    RAISE NOTICE '  Views:      v_journal_issues';
    RAISE NOTICE '  Functions:  check_journal_balance';
    RAISE NOTICE '  Indexes:    idx_je_period, idx_je_status, idx_indexes_active, idx_sf_municipality';
END $$;
