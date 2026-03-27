CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE municipalities (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL,
    code        VARCHAR(20) UNIQUE NOT NULL,
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW()
);

INSERT INTO municipalities (name, code) VALUES
    ('Tel Aviv',     'TLV'),
    ('Galil',        'GAL'),
    ('Haifa',        'HFA'),
    ('Yokneam',      'YOK'),
    ('Beer Sheva',   'BEV'),
    ('Netanya',      'NET');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('accountant','treasurer','admin')),
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_municipality (
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    municipality_id     UUID REFERENCES municipalities(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, municipality_id)
);

CREATE TABLE templates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(50) NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    key_field       VARCHAR(50) NOT NULL,
    municipality_id UUID REFERENCES municipalities(id),
    active          BOOLEAN DEFAULT TRUE
);

INSERT INTO templates (name, display_name, key_field) VALUES
    ('bezeq',       'Bezeq',       'phone'),
    ('electricity', 'Electricity',  'meter'),
    ('welfare',     'Welfare',      'beneficiary');

CREATE TABLE indexes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    municipality_id UUID NOT NULL REFERENCES municipalities(id) ON DELETE CASCADE,
    template_id     UUID NOT NULL REFERENCES templates(id),
    key_value       VARCHAR(100) NOT NULL,
    account_code    VARCHAR(20) NOT NULL,
    description     VARCHAR(200),
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (municipality_id, template_id, key_value)
);

CREATE INDEX idx_indexes_lookup ON indexes (municipality_id, template_id, key_value);

CREATE TABLE journal_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    municipality_id UUID NOT NULL REFERENCES municipalities(id),
    template_id     UUID NOT NULL REFERENCES templates(id),
    period          VARCHAR(7) NOT NULL,
    reference_num   VARCHAR(50),
    status          VARCHAR(20) DEFAULT 'draft'
                        CHECK (status IN ('draft','ready','exported','approved')),
    source_file     VARCHAR(255),
    total_amount    NUMERIC(14,2),
    notes           TEXT,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_je_municipality ON journal_entries (municipality_id, period);

CREATE TABLE journal_lines (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_id    UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    line_num    INTEGER NOT NULL,
    account     VARCHAR(20) NOT NULL,
    description VARCHAR(200),
    debit       NUMERIC(14,2) DEFAULT 0,
    credit      NUMERIC(14,2) DEFAULT 0,
    reference   VARCHAR(100),
    key_value   VARCHAR(100),
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_jl_entry ON journal_lines (entry_id, line_num);

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
