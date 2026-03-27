-- upgrade_v2_fix.sql
-- Fix missing objects from upgrade_v2

-- source_files (failed due to encoding)
CREATE TABLE IF NOT EXISTS source_files (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    municipality_id UUID NOT NULL REFERENCES municipalities(id),
    template_id     UUID NOT NULL REFERENCES templates(id),
    entry_id        UUID REFERENCES journal_entries(id) ON DELETE SET NULL,
    filename        VARCHAR(255) NOT NULL,
    file_size       INTEGER,
    file_hash       VARCHAR(64),
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

CREATE INDEX IF NOT EXISTS idx_sf_municipality ON source_files (municipality_id, period);

-- prevent_locked_edit trigger
CREATE OR REPLACE FUNCTION prevent_locked_edit()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IN ('exported', 'locked') THEN
        RAISE EXCEPTION 'Cannot edit entry with status %', OLD.status;
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

-- v_journal_issues view
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
        WHEN ABS(
            COALESCE((SELECT SUM(jl.debit)  FROM journal_lines jl WHERE jl.entry_id = je.id), 0) -
            COALESCE((SELECT SUM(jl.credit) FROM journal_lines jl WHERE jl.entry_id = je.id), 0)
        ) > 0.10 THEN 'unbalanced'
        WHEN EXISTS (
            SELECT 1 FROM journal_lines jl
            WHERE jl.entry_id = je.id AND (jl.account IS NULL OR jl.account = '9999')
        ) THEN 'missing_account'
        ELSE NULL
    END AS issue_type
FROM journal_entries je
JOIN municipalities m ON m.id = je.municipality_id
WHERE je.status NOT IN ('locked', 'exported');

-- check_journal_balance function
CREATE OR REPLACE FUNCTION check_journal_balance(p_entry_id UUID)
RETURNS TABLE (
    is_balanced  BOOLEAN,
    total_debit  NUMERIC,
    total_credit NUMERIC,
    diff         NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ABS(SUM(jl.debit) - SUM(jl.credit)) <= 0.10,
        SUM(jl.debit),
        SUM(jl.credit),
        ABS(SUM(jl.debit) - SUM(jl.credit))
    FROM journal_lines jl
    WHERE jl.entry_id = p_entry_id;
END;
$$ LANGUAGE plpgsql;

SELECT 'upgrade_v2_fix completed OK' AS status;
