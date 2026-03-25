-- =============================================================================
-- Financial Crime Analytics Platform (FCAP) — PostgreSQL Schema
-- Script 02: Analytical views
-- =============================================================================

-- =============================================================================
-- v_high_risk_entities
-- Entities whose current risk score exceeds the HIGH threshold (70).
-- =============================================================================
CREATE OR REPLACE VIEW v_high_risk_entities AS
SELECT
    e.entity_id,
    e.name,
    e.entity_type,
    e.national_id,
    e.address,
    e.risk_score,
    e.pep_flag,
    e.created_at,
    e.updated_at,
    -- Count of open alerts for context
    COUNT(a.alert_id) FILTER (WHERE a.status = 'OPEN') AS open_alert_count,
    -- Latest scoring timestamp
    MAX(rsh.scoring_timestamp)                          AS last_scored_at
FROM entities e
LEFT JOIN alerts             a   ON a.entity_id   = e.entity_id
LEFT JOIN risk_scores_history rsh ON rsh.entity_id = e.entity_id
WHERE e.risk_score > 70
GROUP BY
    e.entity_id,
    e.name,
    e.entity_type,
    e.national_id,
    e.address,
    e.risk_score,
    e.pep_flag,
    e.created_at,
    e.updated_at;

-- =============================================================================
-- v_open_alerts_by_type
-- Count and average risk score of open alerts, grouped by alert type.
-- =============================================================================
CREATE OR REPLACE VIEW v_open_alerts_by_type AS
SELECT
    alert_type,
    COUNT(*)                        AS alert_count,
    ROUND(AVG(risk_score), 2)       AS avg_risk_score,
    ROUND(MAX(risk_score), 2)       AS max_risk_score,
    MIN(created_at)                 AS oldest_open_alert,
    MAX(created_at)                 AS newest_open_alert
FROM alerts
WHERE status = 'OPEN'
GROUP BY alert_type
ORDER BY alert_count DESC;

-- =============================================================================
-- v_suspicious_transaction_pairs
-- Pairs of transactions where the same entity sends then receives money
-- within a 24-hour window (potential round-tripping / rapid movement).
-- =============================================================================
CREATE OR REPLACE VIEW v_suspicious_transaction_pairs AS
WITH entity_transactions AS (
    -- Outgoing transactions with entity context
    SELECT
        e.entity_id,
        e.name                          AS entity_name,
        t_out.transaction_id            AS outgoing_txn_id,
        t_out.amount                    AS outgoing_amount,
        t_out.currency                  AS outgoing_currency,
        t_out.destination_account_id    AS intermediary_account_id,
        t_out.transaction_timestamp     AS outgoing_ts
    FROM transactions t_out
    JOIN accounts      a_out ON a_out.account_id = t_out.source_account_id
    JOIN entities      e     ON e.entity_id      = a_out.entity_id
    WHERE t_out.status = 'COMPLETED'
)
SELECT
    et_out.entity_id,
    et_out.entity_name,
    et_out.outgoing_txn_id,
    et_out.outgoing_amount,
    et_out.outgoing_currency,
    et_out.outgoing_ts,
    t_in.transaction_id             AS incoming_txn_id,
    t_in.amount                     AS incoming_amount,
    t_in.transaction_timestamp      AS incoming_ts,
    EXTRACT(EPOCH FROM (t_in.transaction_timestamp - et_out.outgoing_ts)) / 3600
                                    AS hours_between_transactions
FROM entity_transactions et_out
JOIN transactions t_in
    ON  t_in.destination_account_id = et_out.intermediary_account_id
    AND t_in.transaction_timestamp   > et_out.outgoing_ts
    AND t_in.transaction_timestamp  <= et_out.outgoing_ts + INTERVAL '24 hours'
JOIN accounts a_in ON a_in.account_id = t_in.source_account_id
WHERE t_in.status     = 'COMPLETED'
  AND a_in.entity_id <> et_out.entity_id   -- different entity in the middle
ORDER BY et_out.entity_name, et_out.outgoing_ts;

-- =============================================================================
-- v_investigation_summary
-- Full case summary for investigator dashboards.
-- =============================================================================
CREATE OR REPLACE VIEW v_investigation_summary AS
SELECT
    ic.case_id,
    ic.status                                               AS case_status,
    ic.priority,
    ic.assigned_to,
    ic.opened_at,
    ic.closed_at,
    EXTRACT(DAY FROM (COALESCE(ic.closed_at, now()) - ic.opened_at))::INT
                                                            AS age_days,
    a.alert_id,
    a.alert_type,
    a.risk_score                                            AS alert_risk_score,
    a.status                                                AS alert_status,
    a.description                                           AS alert_description,
    a.created_at                                            AS alert_created_at,
    e.entity_id,
    e.name                                                  AS entity_name,
    e.entity_type,
    e.risk_score                                            AS entity_risk_score,
    e.pep_flag
FROM investigation_cases ic
JOIN alerts   a ON a.alert_id  = ic.alert_id
JOIN entities e ON e.entity_id = a.entity_id
ORDER BY ic.priority DESC, ic.opened_at ASC;
