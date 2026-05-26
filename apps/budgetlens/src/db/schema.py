from sqlalchemy import text

DDL = """
CREATE SCHEMA IF NOT EXISTS budgetlens;

-- Staging table: append-only, every import adds rows regardless of duplicates.
-- content_hash is stored for the dedup view but has no UNIQUE constraint here.
CREATE TABLE IF NOT EXISTS budgetlens.transactions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source               VARCHAR(10)   NOT NULL,
    transaction_date     DATE          NOT NULL,
    post_date            DATE,
    description          TEXT          NOT NULL,
    original_description TEXT          NOT NULL,
    category             VARCHAR(50)   NOT NULL,
    category_overridden  BOOLEAN       NOT NULL DEFAULT FALSE,
    transaction_type     VARCHAR(20),
    amount               NUMERIC(12,2) NOT NULL,
    memo                 TEXT,
    running_balance      NUMERIC(12,2),
    bill_id              UUID,
    imported_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    content_hash         VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS budgetlens.bills (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name               TEXT          NOT NULL,
    category           VARCHAR(50)   NOT NULL,
    frequency          VARCHAR(20)   NOT NULL,
    amount             NUMERIC(12,2) NOT NULL,
    monthly_equivalent NUMERIC(12,2) NOT NULL,
    start_date         DATE          NOT NULL,
    last_charge_date   DATE,
    next_charge_date   DATE,
    active             BOOLEAN       NOT NULL DEFAULT TRUE,
    notes              TEXT,
    created_at         TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS budgetlens.bill_transactions (
    bill_id        UUID REFERENCES budgetlens.bills(id) ON DELETE CASCADE,
    transaction_id UUID REFERENCES budgetlens.transactions(id) ON DELETE CASCADE,
    PRIMARY KEY (bill_id, transaction_id)
);

CREATE TABLE IF NOT EXISTS budgetlens.budget_categories (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id   VARCHAR(50)   NOT NULL UNIQUE,
    monthly_limit NUMERIC(12,2) NOT NULL,
    rollover      BOOLEAN       NOT NULL DEFAULT FALSE,
    budget_type   VARCHAR(10)   NOT NULL DEFAULT 'variable',
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS budgetlens.savings_goals (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                 TEXT          NOT NULL,
    target_amount        NUMERIC(12,2) NOT NULL,
    target_date          DATE          NOT NULL,
    current_amount       NUMERIC(12,2) NOT NULL DEFAULT 0,
    monthly_contribution NUMERIC(12,2),
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS budgetlens.settings (
    key   VARCHAR(100) PRIMARY KEY,
    value TEXT         NOT NULL
);

INSERT INTO budgetlens.settings (key, value) VALUES
    ('monthly_income_estimate', '0'),
    ('alert_threshold_percent', '80'),
    ('due_soon_days_threshold', '5'),
    ('pay_cadence', 'semi_monthly')
ON CONFLICT (key) DO NOTHING;

-- Marks which transaction descriptions count as regular income.
CREATE TABLE IF NOT EXISTS budgetlens.income_transaction_rules (
    description TEXT PRIMARY KEY,
    is_regular  BOOLEAN NOT NULL DEFAULT TRUE
);

-- Manual income sources not derived from transactions.
CREATE TABLE IF NOT EXISTS budgetlens.income_sources (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT          NOT NULL,
    amount     NUMERIC(12,2) NOT NULL,
    cadence    VARCHAR(20)   NOT NULL,
    active     BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
"""

DEDUP_VIEW = """
CREATE OR REPLACE VIEW budgetlens.transactions_deduped AS
SELECT DISTINCT ON (content_hash)
    id, source, transaction_date, post_date, description, original_description,
    category, category_overridden, transaction_type, amount, memo,
    running_balance, bill_id, imported_at, content_hash
FROM budgetlens.transactions
ORDER BY content_hash, imported_at DESC;
"""

DROP_UNIQUE = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'transactions_content_hash_key'
          AND conrelid = 'budgetlens.transactions'::regclass
    ) THEN
        ALTER TABLE budgetlens.transactions
            DROP CONSTRAINT transactions_content_hash_key;
    END IF;
END
$$;
"""

FREQUENCY_MIGRATION = """
ALTER TABLE budgetlens.bills ADD COLUMN IF NOT EXISTS frequency_count INTEGER NOT NULL DEFAULT 1;

UPDATE budgetlens.bills SET frequency = 'weeks',  frequency_count = 1  WHERE frequency = 'weekly';
UPDATE budgetlens.bills SET frequency = 'months', frequency_count = 1  WHERE frequency = 'monthly';
UPDATE budgetlens.bills SET frequency = 'months', frequency_count = 2  WHERE frequency = 'every_2_months';
UPDATE budgetlens.bills SET frequency = 'months', frequency_count = 3  WHERE frequency = 'quarterly';
UPDATE budgetlens.bills SET frequency = 'months', frequency_count = 6  WHERE frequency = 'every_6_months';
UPDATE budgetlens.bills SET frequency = 'years',  frequency_count = 1  WHERE frequency = 'yearly';
"""

INCOME_MIGRATION = """
ALTER TABLE budgetlens.income_transaction_rules
    ADD COLUMN IF NOT EXISTS name_override   TEXT,
    ADD COLUMN IF NOT EXISTS cadence         VARCHAR(20),
    ADD COLUMN IF NOT EXISTS amount_override NUMERIC(12,2);

CREATE TABLE IF NOT EXISTS budgetlens.income_excluded_hashes (
    content_hash VARCHAR(64) PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS budgetlens.income_transaction_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alias           TEXT          NOT NULL,
    filter_type     VARCHAR(20)   NOT NULL DEFAULT 'contains',
    filter_value    TEXT          NOT NULL,
    cadence         VARCHAR(20)   NOT NULL DEFAULT 'semi_monthly',
    amount_override NUMERIC(12,2),
    active          BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS budgetlens.income_source_excluded_hashes (
    source_id    UUID        NOT NULL REFERENCES budgetlens.income_transaction_sources(id) ON DELETE CASCADE,
    content_hash VARCHAR(64) NOT NULL,
    PRIMARY KEY (source_id, content_hash)
);
"""

BILL_FILTER_MIGRATION = """
ALTER TABLE budgetlens.bills
    ADD COLUMN IF NOT EXISTS filter_type        VARCHAR(20) DEFAULT 'contains',
    ADD COLUMN IF NOT EXISTS filter_value       TEXT,
    ADD COLUMN IF NOT EXISTS aggregation_method VARCHAR(20) DEFAULT 'average';

CREATE TABLE IF NOT EXISTS budgetlens.bill_excluded_hashes (
    bill_id      UUID        NOT NULL REFERENCES budgetlens.bills(id) ON DELETE CASCADE,
    content_hash VARCHAR(64) NOT NULL,
    PRIMARY KEY (bill_id, content_hash)
);
"""

ENTITY_MIGRATION = """
DO $$
BEGIN
    -- Create entities table if not already done
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables WHERE schemaname = 'budgetlens' AND tablename = 'entities'
    ) THEN
        CREATE TABLE budgetlens.entities (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name        TEXT    NOT NULL,
            description TEXT,
            is_default  BOOLEAN NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    END IF;

    -- Migrate from profiles table if it still exists (old schema)
    IF EXISTS (
        SELECT 1 FROM pg_tables WHERE schemaname = 'budgetlens' AND tablename = 'profiles'
    ) THEN
        INSERT INTO budgetlens.entities (id, name, description, is_default, created_at)
        SELECT id, name, description, is_default, created_at FROM budgetlens.profiles
        ON CONFLICT (id) DO NOTHING;

        ALTER TABLE budgetlens.bills
            ADD COLUMN IF NOT EXISTS entity_id UUID REFERENCES budgetlens.entities(id) ON DELETE SET NULL;
        ALTER TABLE budgetlens.income_transaction_sources
            ADD COLUMN IF NOT EXISTS entity_id UUID REFERENCES budgetlens.entities(id) ON DELETE SET NULL;
        ALTER TABLE budgetlens.income_sources
            ADD COLUMN IF NOT EXISTS entity_id UUID REFERENCES budgetlens.entities(id) ON DELETE SET NULL;

        UPDATE budgetlens.bills SET entity_id = profile_id WHERE entity_id IS NULL AND profile_id IS NOT NULL;
        UPDATE budgetlens.income_transaction_sources SET entity_id = profile_id WHERE entity_id IS NULL AND profile_id IS NOT NULL;
        UPDATE budgetlens.income_sources SET entity_id = profile_id WHERE entity_id IS NULL AND profile_id IS NOT NULL;

        ALTER TABLE budgetlens.bills DROP COLUMN IF EXISTS profile_id;
        ALTER TABLE budgetlens.income_transaction_sources DROP COLUMN IF EXISTS profile_id;
        ALTER TABLE budgetlens.income_sources DROP COLUMN IF EXISTS profile_id;

        DROP TABLE budgetlens.profiles;
    END IF;

    -- Ensure entity_id columns exist (fresh installs where profiles never existed)
    ALTER TABLE budgetlens.bills
        ADD COLUMN IF NOT EXISTS entity_id UUID REFERENCES budgetlens.entities(id) ON DELETE SET NULL;
    ALTER TABLE budgetlens.income_transaction_sources
        ADD COLUMN IF NOT EXISTS entity_id UUID REFERENCES budgetlens.entities(id) ON DELETE SET NULL;
    ALTER TABLE budgetlens.income_sources
        ADD COLUMN IF NOT EXISTS entity_id UUID REFERENCES budgetlens.entities(id) ON DELETE SET NULL;
END
$$;

-- Manual expenses per entity (recurring and one-time, outside bank transactions)
CREATE TABLE IF NOT EXISTS budgetlens.entity_expenses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES budgetlens.entities(id) ON DELETE CASCADE,
    name            TEXT          NOT NULL,
    amount          NUMERIC(12,2) NOT NULL,
    is_recurring    BOOLEAN       NOT NULL DEFAULT FALSE,
    frequency       VARCHAR(20),
    frequency_count INTEGER       NOT NULL DEFAULT 1,
    expense_date    DATE,
    start_date      DATE,
    end_date        DATE,
    category        VARCHAR(50)   NOT NULL DEFAULT 'uncategorized',
    notes           TEXT,
    active          BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- One-time transaction links: attach specific bank transactions to an entity
CREATE TABLE IF NOT EXISTS budgetlens.entity_transaction_links (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id      UUID NOT NULL REFERENCES budgetlens.entities(id) ON DELETE CASCADE,
    transaction_id UUID NOT NULL REFERENCES budgetlens.transactions(id) ON DELETE CASCADE,
    notes          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entity_id, transaction_id)
);
"""


def init_schema(engine):
    def _run(sql: str):
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()

    _run(DDL)
    _run(DROP_UNIQUE)
    _run(DEDUP_VIEW)
    _run(FREQUENCY_MIGRATION)
    _run(INCOME_MIGRATION)
    _run(BILL_FILTER_MIGRATION)
    _run(ENTITY_MIGRATION)
