-- =============================================
-- יומנית – PostgreSQL Schema
-- Multi-Tenant Journal Entry System
-- =============================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- MUNICIPALITIES
-- =============================================
CREATE TABLE municipalities (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL,
    code        VARCHAR(20) UNIQUE NOT NULL,  -- קוד רשות רשמי
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW()
);

INSERT INTO municipalities (name, code) VALUES
    ('עיריית תל אביב',        'TLV'),
    ('מועצה אזורית גליל',    'GAL'),
    ('עיריית חיפה',           'HFA'),
    ('מועצה מקומית יוקנעם',  'YOK'),
    ('עיריית באר שבע',        'BEV'),
    ('עיריית נתניה',          'NET');

-- =============================================
-- USERS
-- =============================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('accountant','treasurer','admin')),
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- USER ↔ MUNICIPALITY (many-to-many)
-- =============================================
CREATE TABLE user_municipality (
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    municipality_id     UUID REFERENCES municipalities(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, municipality_id)
);

-- =============================================
-- TEMPLATES  (סוגי פקודות)
-- =============================================
CREATE TABLE templates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(50) NOT NULL,          -- 'bezeq' | 'electricity' | 'welfare'
    display_name    VARCHAR(100) NOT NULL,
    key_field       VARCHAR(50) NOT NULL,          -- 'phone' | 'meter' | 'beneficiary'
    municipality_id UUID REFERENCES municipalities(id),  -- NULL = global
    active          BOOLEAN DEFAULT TRUE
);

INSERT INTO templates (name, display_name, key_field) VALUES
    ('bezeq',       'בזק – טלפוניה',   'phone'),
    ('electricity', 'חשמל – מונים',    'meter'),
    ('welfare',     'רווחה – זכאים',   'beneficiary');

-- =============================================
-- INDEXES  (מפתחות שיוך)
-- phone → account_code, meter → account_code, etc.
-- =============================================
CREATE TABLE indexes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    municipality_id UUID NOT NULL REFERENCES municipalities(id) ON DELETE CASCADE,
    template_id     UUID NOT NULL REFERENCES templates(id),
    key_value       VARCHAR(100) NOT NULL,   -- מספר טלפון / מונה / ת"ז
    account_code    VARCHAR(20) NOT NULL,    -- קוד חשבון בנה"ח
    description     VARCHAR(200),
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (municipality_id, template_id, key_value)
);

CREATE INDEX idx_indexes_lookup
    ON indexes (municipality_id, template_id, key_value);

-- =============================================
-- JOURNAL ENTRIES  (פקודות יומן – header)
-- =============================================
CREATE TABLE journal_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    municipality_id UUID NOT NULL REFERENCES municipalities(id),
    template_id     UUID NOT NULL REFERENCES templates(id),
    period          VARCHAR(7) NOT NULL,    -- 'YYYY-MM'  e.g. '2025-03'
    reference_num   VARCHAR(50),            -- מספר פקודה פנימי
    status          VARCHAR(20) DEFAULT 'draft'
                        CHECK (status IN ('draft','ready','exported','approved')),
    source_file     VARCHAR(255),           -- שם קובץ מקור
    total_amount    NUMERIC(14,2),
    notes           TEXT,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_je_municipality ON journal_entries (municipality_id, period);

-- =============================================
-- JOURNAL LINES  (שורות פקודה)
-- =============================================
CREATE TABLE journal_lines (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_id    UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    line_num    INTEGER NOT NULL,
    account     VARCHAR(20) NOT NULL,
    description VARCHAR(200),
    debit       NUMERIC(14,2) DEFAULT 0,
    credit      NUMERIC(14,2) DEFAULT 0,
    reference   VARCHAR(100),   -- מספר חשבונית / אסמכתא
    key_value   VARCHAR(100),   -- מספר טלפון / מונה (לעקיבה)
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_jl_entry ON journal_lines (entry_id, line_num);

-- =============================================
-- UPLOAD LOG  (תיעוד קבצים שנטענו)
-- =============================================
CREATE TABLE upload_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    municipality_id UUID REFERENCES municipalities(id),
    template_id     UUID REFERENCES templates(id),
    filename        VARCHAR(255),
    row_count       INTEGER,
    matched_count   INTEGER,
    missing_count   INTEGER,
    uploaded_by     UUID REFERENCES users(id),
    entry_id        UUID REFERENCES journal_entries(id),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- =============================================
-- HELPER: auto-update updated_at
-- =============================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_je_updated
    BEFORE UPDATE ON journal_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_idx_updated
    BEFORE UPDATE ON indexes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
