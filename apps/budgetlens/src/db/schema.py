from .connection import execute

DDL = """
CREATE SCHEMA IF NOT EXISTS budgetlens;

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
    content_hash         VARCHAR(64)   UNIQUE
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
    ('due_soon_days_threshold', '5')
ON CONFLICT (key) DO NOTHING;
"""


def init_schema():
    execute(DDL)
