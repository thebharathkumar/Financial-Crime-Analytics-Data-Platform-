-- =============================================================================
-- Financial Crime Analytics Platform (FCAP)
-- Investigative Workflow Queries
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. GET ALL OPEN CASES WITH FULL ENTITY AND ALERT DETAILS
--    Returns a complete picture for the investigator queue.
-- ---------------------------------------------------------------------------
SELECT
    ic.case_id,
    ic.priority,
    ic.status                                               AS case_status,
    ic.assigned_to,
    ic.opened_at,
    EXTRACT(DAY FROM (now() - ic.opened_at))::INT           AS age_days,
    ic.notes,

    a.alert_id,
    a.alert_type,
    a.risk_score                                            AS alert_risk_score,
    a.status                                                AS alert_status,
    a.description                                           AS alert_description,
    a.created_by,
    a.created_at                                            AS alert_created_at,

    e.entity_id,
    e.name                                                  AS entity_name,
    e.entity_type,
    e.national_id,
    e.risk_score                                            AS entity_risk_score,
    e.pep_flag,

    -- Related transaction details (optional)
    t.transaction_id,
    t.amount                                                AS txn_amount,
    t.currency,
    t.transaction_type,
    t.transaction_timestamp

FROM investigation_cases ic
JOIN alerts       a  ON a.alert_id     = ic.alert_id
JOIN entities     e  ON e.entity_id    = a.entity_id
LEFT JOIN transactions t ON t.transaction_id = a.transaction_id
WHERE ic.status NOT IN ('CLOSED_SAR', 'CLOSED_NO_ACTION')
ORDER BY
    CASE ic.priority
        WHEN 'CRITICAL' THEN 1
        WHEN 'HIGH'     THEN 2
        WHEN 'MEDIUM'   THEN 3
        WHEN 'LOW'      THEN 4
        ELSE 5
    END,
    ic.opened_at ASC;


-- ---------------------------------------------------------------------------
-- 2. ASSIGN CASE TO INVESTIGATOR
--    Updates the assigned_to field and sets status to IN_PROGRESS.
--    Replace :case_id and :investigator_username with actual values.
-- ---------------------------------------------------------------------------
UPDATE investigation_cases
SET
    assigned_to = :investigator_username,
    status      = 'IN_PROGRESS',
    notes       = COALESCE(notes, '') ||
                  E'\n[' || now()::TEXT || '] Assigned to ' || :investigator_username
WHERE case_id = :case_id
  AND status  = 'NEW'
RETURNING
    case_id,
    assigned_to,
    status,
    opened_at;


-- ---------------------------------------------------------------------------
-- 3. CLOSE CASE WITH RESOLUTION
--    Supports two closure types: SAR filed, or no action taken.
--    Also propagates status back to the related alert.
--    Replace :case_id, :resolution, :closure_notes with actual values.
--    :resolution must be 'CLOSED_SAR' or 'CLOSED_NO_ACTION'.
-- ---------------------------------------------------------------------------
WITH closed_case AS (
    UPDATE investigation_cases
    SET
        status    = :resolution,
        closed_at = now(),
        notes     = COALESCE(notes, '') ||
                    E'\n[' || now()::TEXT || '] Closed: ' || :closure_notes
    WHERE case_id = :case_id
      AND status NOT IN ('CLOSED_SAR', 'CLOSED_NO_ACTION')
    RETURNING case_id, alert_id, status
)
UPDATE alerts a
SET
    status     = CASE WHEN cc.status = 'CLOSED_SAR' THEN 'ESCALATED' ELSE 'CLOSED' END,
    updated_at = now()
FROM closed_case cc
WHERE a.alert_id = cc.alert_id
RETURNING a.alert_id, a.status;


-- ---------------------------------------------------------------------------
-- 4. CASE AGING REPORT
--    Returns all cases that have been open for more than 30 days without
--    closure, sorted by age descending (most overdue first).
-- ---------------------------------------------------------------------------
SELECT
    ic.case_id,
    ic.priority,
    ic.status,
    ic.assigned_to,
    ic.opened_at,
    EXTRACT(DAY FROM (now() - ic.opened_at))::INT           AS age_days,
    a.alert_type,
    a.risk_score                                            AS alert_risk_score,
    e.name                                                  AS entity_name,
    e.risk_score                                            AS entity_risk_score
FROM investigation_cases ic
JOIN alerts   a ON a.alert_id  = ic.alert_id
JOIN entities e ON e.entity_id = a.entity_id
WHERE ic.status NOT IN ('CLOSED_SAR', 'CLOSED_NO_ACTION')
  AND ic.opened_at < now() - INTERVAL '30 days'
ORDER BY age_days DESC, ic.priority DESC;


-- ---------------------------------------------------------------------------
-- 5. ENTITY TRANSACTION HISTORY WITH RUNNING TOTAL
--    Full chronological transaction log for an entity with a running
--    cumulative balance (sum of outgoing amounts).
--    Replace :entity_id with the target entity UUID.
-- ---------------------------------------------------------------------------
SELECT
    t.transaction_id,
    t.transaction_timestamp,
    t.transaction_type,
    acct_src.account_number                                 AS source_account,
    acct_dst.account_number                                 AS destination_account,
    ent_dst.name                                            AS counterparty_name,
    t.amount,
    t.currency,
    t.risk_score,
    t.flagged,
    SUM(t.amount) OVER (
        PARTITION BY acct_src.entity_id
        ORDER BY t.transaction_timestamp
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                       AS running_total_outgoing,
    COUNT(*) OVER (
        PARTITION BY acct_src.entity_id
        ORDER BY t.transaction_timestamp
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )                                                       AS txn_sequence_number
FROM transactions t
JOIN accounts acct_src ON acct_src.account_id = t.source_account_id
JOIN accounts acct_dst ON acct_dst.account_id = t.destination_account_id
JOIN entities ent_dst  ON ent_dst.entity_id   = acct_dst.entity_id
WHERE acct_src.entity_id = :entity_id
  AND t.status           = 'COMPLETED'
ORDER BY t.transaction_timestamp ASC;
