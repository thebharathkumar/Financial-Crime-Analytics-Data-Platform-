-- =============================================================================
-- Financial Crime Analytics Platform (FCAP) — PostgreSQL Schema
-- Script 01: Core table definitions
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENTITIES
-- Represents individuals, companies, or trusts under AML monitoring.
-- =============================================================================
CREATE TABLE IF NOT EXISTS entities (
    entity_id       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(500)  NOT NULL,
    entity_type     VARCHAR(50)   NOT NULL
                        CHECK (entity_type IN ('INDIVIDUAL', 'CORPORATE', 'TRUST', 'GOVERNMENT', 'OTHER')),
    national_id     VARCHAR(100),
    address         TEXT,
    risk_score      NUMERIC(5,2)  NOT NULL DEFAULT 0.00
                        CHECK (risk_score >= 0 AND risk_score <= 100),
    pep_flag        BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entities_name          ON entities (name);
CREATE INDEX IF NOT EXISTS idx_entities_national_id   ON entities (national_id)  WHERE national_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_entities_risk_score    ON entities (risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_entities_pep_flag      ON entities (pep_flag)     WHERE pep_flag IS TRUE;

-- =============================================================================
-- ACCOUNTS
-- Bank or payment accounts linked to entities.
-- =============================================================================
CREATE TABLE IF NOT EXISTS accounts (
    account_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID          NOT NULL REFERENCES entities(entity_id) ON DELETE RESTRICT,
    account_number  VARCHAR(50)   NOT NULL UNIQUE,
    account_type    VARCHAR(50)   NOT NULL
                        CHECK (account_type IN ('CURRENT', 'SAVINGS', 'CORRESPONDENT', 'NOSTRO', 'VOSTRO', 'OTHER')),
    status          VARCHAR(20)   NOT NULL DEFAULT 'ACTIVE'
                        CHECK (status IN ('ACTIVE', 'DORMANT', 'FROZEN', 'CLOSED')),
    opened_at       DATE,
    country_code    CHAR(2)
);

CREATE INDEX IF NOT EXISTS idx_accounts_entity_id      ON accounts (entity_id);
CREATE INDEX IF NOT EXISTS idx_accounts_account_number ON accounts (account_number);
CREATE INDEX IF NOT EXISTS idx_accounts_country_code   ON accounts (country_code);
CREATE INDEX IF NOT EXISTS idx_accounts_status         ON accounts (status);

-- =============================================================================
-- TRANSACTIONS
-- Financial movements between accounts.
-- =============================================================================
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id          UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    source_account_id       UUID           NOT NULL REFERENCES accounts(account_id) ON DELETE RESTRICT,
    destination_account_id  UUID           NOT NULL REFERENCES accounts(account_id) ON DELETE RESTRICT,
    amount                  NUMERIC(20,4)  NOT NULL CHECK (amount > 0),
    currency                CHAR(3)        NOT NULL,
    transaction_type        VARCHAR(50)    NOT NULL
                                CHECK (transaction_type IN (
                                    'WIRE', 'ACH', 'SWIFT', 'INTERNAL', 'CASH', 'CHEQUE', 'CRYPTO', 'OTHER'
                                )),
    status                  VARCHAR(30)    NOT NULL DEFAULT 'COMPLETED'
                                CHECK (status IN ('PENDING', 'COMPLETED', 'FAILED', 'REVERSED', 'UNDER_REVIEW')),
    transaction_timestamp   TIMESTAMPTZ    NOT NULL,
    risk_score              NUMERIC(5,2)   CHECK (risk_score >= 0 AND risk_score <= 100),
    flagged                 BOOLEAN        NOT NULL DEFAULT FALSE,
    created_at              TIMESTAMPTZ    NOT NULL DEFAULT now(),
    CONSTRAINT chk_no_self_transfer
        CHECK (source_account_id <> destination_account_id)
);

CREATE INDEX IF NOT EXISTS idx_transactions_source_account      ON transactions (source_account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_destination_account ON transactions (destination_account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_timestamp           ON transactions (transaction_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_flagged             ON transactions (flagged) WHERE flagged IS TRUE;
CREATE INDEX IF NOT EXISTS idx_transactions_risk_score          ON transactions (risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_currency            ON transactions (currency);
CREATE INDEX IF NOT EXISTS idx_transactions_status              ON transactions (status);

-- =============================================================================
-- ALERTS
-- AML alerts raised against entities or specific transactions.
-- =============================================================================
CREATE TABLE IF NOT EXISTS alerts (
    alert_id        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID          NOT NULL REFERENCES entities(entity_id) ON DELETE RESTRICT,
    transaction_id  UUID          REFERENCES transactions(transaction_id) ON DELETE SET NULL,
    alert_type      VARCHAR(50)   NOT NULL
                        CHECK (alert_type IN ('STRUCTURING', 'LAYERING', 'RAPID_MOVEMENT', 'HIGH_VALUE',
                                              'GEOGRAPHY', 'PEP', 'ADVERSE_MEDIA', 'NETWORK_ANOMALY')),
    risk_score      NUMERIC(5,2)  NOT NULL CHECK (risk_score >= 0 AND risk_score <= 100),
    status          VARCHAR(30)   NOT NULL DEFAULT 'OPEN'
                        CHECK (status IN ('OPEN', 'UNDER_REVIEW', 'CLOSED', 'ESCALATED', 'FALSE_POSITIVE')),
    description     TEXT,
    created_by      VARCHAR(100)  NOT NULL DEFAULT 'SYSTEM',
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alerts_entity_id      ON alerts (entity_id);
CREATE INDEX IF NOT EXISTS idx_alerts_transaction_id ON alerts (transaction_id)  WHERE transaction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_alert_type     ON alerts (alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_status         ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at     ON alerts (created_at DESC);

-- =============================================================================
-- INVESTIGATION CASES
-- Workflow management for alert investigations.
-- =============================================================================
CREATE TABLE IF NOT EXISTS investigation_cases (
    case_id         UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id        UUID          NOT NULL REFERENCES alerts(alert_id) ON DELETE RESTRICT,
    assigned_to     VARCHAR(100),
    status          VARCHAR(30)   NOT NULL DEFAULT 'NEW'
                        CHECK (status IN ('NEW', 'IN_PROGRESS', 'PENDING_INFO', 'CLOSED_SAR',
                                          'CLOSED_NO_ACTION', 'ESCALATED_TO_COMPLIANCE')),
    priority        VARCHAR(10)   NOT NULL DEFAULT 'MEDIUM'
                        CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    notes           TEXT,
    opened_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cases_alert_id     ON investigation_cases (alert_id);
CREATE INDEX IF NOT EXISTS idx_cases_assigned_to  ON investigation_cases (assigned_to) WHERE assigned_to IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cases_status       ON investigation_cases (status);
CREATE INDEX IF NOT EXISTS idx_cases_priority     ON investigation_cases (priority);
CREATE INDEX IF NOT EXISTS idx_cases_opened_at    ON investigation_cases (opened_at DESC);

-- =============================================================================
-- RISK SCORES HISTORY
-- Immutable audit log of entity risk score changes.
-- =============================================================================
CREATE TABLE IF NOT EXISTS risk_scores_history (
    id                   SERIAL        PRIMARY KEY,
    entity_id            UUID          NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    score                NUMERIC(5,2)  NOT NULL CHECK (score >= 0 AND score <= 100),
    risk_level           VARCHAR(10)   NOT NULL
                             CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    scoring_timestamp    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    contributing_factors JSONB
);

CREATE INDEX IF NOT EXISTS idx_risk_history_entity_id  ON risk_scores_history (entity_id);
CREATE INDEX IF NOT EXISTS idx_risk_history_timestamp  ON risk_scores_history (scoring_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_risk_history_risk_level ON risk_scores_history (risk_level);
-- GIN index for JSONB queries on contributing factors
CREATE INDEX IF NOT EXISTS idx_risk_history_factors    ON risk_scores_history USING GIN (contributing_factors);
