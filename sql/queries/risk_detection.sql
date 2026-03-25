-- =============================================================================
-- Financial Crime Analytics Platform (FCAP)
-- Risk Detection Queries
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. STRUCTURING PATTERN DETECTION
--    Find accounts with multiple transactions just under 10,000 within 7 days.
--    A minimum of 2 qualifying transactions flags the pattern.
-- ---------------------------------------------------------------------------
SELECT
    a.account_number,
    e.entity_id,
    e.name                                  AS entity_name,
    COUNT(t.transaction_id)                 AS near_threshold_txn_count,
    SUM(t.amount)                           AS total_structured_amount,
    MIN(t.transaction_timestamp)            AS window_start,
    MAX(t.transaction_timestamp)            AS window_end,
    MAX(t.transaction_timestamp) - MIN(t.transaction_timestamp)
                                            AS window_span
FROM transactions t
JOIN accounts a ON a.account_id = t.source_account_id
JOIN entities e ON e.entity_id  = a.entity_id
WHERE t.amount         >= 9000
  AND t.amount          < 10000
  AND t.status          = 'COMPLETED'
  AND t.transaction_timestamp >= now() - INTERVAL '7 days'
GROUP BY a.account_number, e.entity_id, e.name
HAVING COUNT(t.transaction_id) >= 2
ORDER BY near_threshold_txn_count DESC, total_structured_amount DESC;


-- ---------------------------------------------------------------------------
-- 2. ROUND-TRIP TRANSACTION DETECTION
--    Money that leaves an entity's account and returns within 30 days
--    via a different intermediary account.
-- ---------------------------------------------------------------------------
WITH outgoing AS (
    SELECT
        e.entity_id,
        e.name              AS entity_name,
        t_out.transaction_id,
        t_out.amount,
        t_out.currency,
        t_out.destination_account_id,
        t_out.transaction_timestamp AS sent_at
    FROM transactions t_out
    JOIN accounts a_src ON a_src.account_id = t_out.source_account_id
    JOIN entities e     ON e.entity_id       = a_src.entity_id
    WHERE t_out.status = 'COMPLETED'
),
returning AS (
    SELECT
        e.entity_id,
        t_in.transaction_id,
        t_in.amount,
        t_in.source_account_id,
        t_in.transaction_timestamp AS received_at
    FROM transactions t_in
    JOIN accounts a_dst ON a_dst.account_id = t_in.destination_account_id
    JOIN entities e     ON e.entity_id       = a_dst.entity_id
    WHERE t_in.status = 'COMPLETED'
)
SELECT
    o.entity_id,
    o.entity_name,
    o.transaction_id        AS outgoing_txn_id,
    o.amount                AS outgoing_amount,
    o.currency,
    o.sent_at,
    r.transaction_id        AS return_txn_id,
    r.amount                AS return_amount,
    r.received_at,
    ROUND(EXTRACT(EPOCH FROM (r.received_at - o.sent_at)) / 86400, 1)
                            AS days_between
FROM outgoing o
JOIN returning r
    ON  r.entity_id     = o.entity_id
    AND r.received_at   > o.sent_at
    AND r.received_at  <= o.sent_at + INTERVAL '30 days'
    AND r.source_account_id = o.destination_account_id   -- returned from same intermediary
    AND ABS(r.amount - o.amount) / NULLIF(o.amount, 0) < 0.10  -- within 10% of original
ORDER BY o.entity_name, o.sent_at;


-- ---------------------------------------------------------------------------
-- 3. HIGH-VELOCITY ACCOUNTS
--    Accounts with more than 50 transactions in any 24-hour window.
-- ---------------------------------------------------------------------------
SELECT
    a.account_number,
    e.entity_id,
    e.name                              AS entity_name,
    DATE_TRUNC('hour', t.transaction_timestamp) AS hour_bucket,
    COUNT(t.transaction_id)             AS txn_count_in_window,
    SUM(t.amount)                       AS total_amount_in_window
FROM transactions t
JOIN accounts a ON a.account_id = t.source_account_id
JOIN entities e ON e.entity_id  = a.entity_id
WHERE t.status = 'COMPLETED'
  AND t.transaction_timestamp >= now() - INTERVAL '7 days'
GROUP BY
    a.account_number,
    e.entity_id,
    e.name,
    DATE_TRUNC('hour', t.transaction_timestamp)
HAVING COUNT(t.transaction_id) > 50
ORDER BY txn_count_in_window DESC;


-- ---------------------------------------------------------------------------
-- 4. HIGH-RISK COUNTRY TRANSACTIONS
--    Transactions to/from a hardcoded list of high-risk jurisdictions
--    (FATF grey/black list, per current guidance).
-- ---------------------------------------------------------------------------
WITH high_risk_countries (country_code) AS (
    VALUES
        ('AF'), ('BY'), ('CF'), ('CD'), ('CG'), ('GN'), ('HT'),
        ('IR'), ('IQ'), ('KP'), ('LY'), ('ML'), ('MM'), ('NI'),
        ('PK'), ('PA'), ('RU'), ('SO'), ('SS'), ('SY'), ('VE'),
        ('YE'), ('ZW')
)
SELECT
    t.transaction_id,
    t.amount,
    t.currency,
    t.transaction_timestamp,
    t.transaction_type,
    src_acct.account_number     AS source_account,
    src_ent.name                AS source_entity,
    src_acct.country_code       AS source_country,
    dst_acct.account_number     AS destination_account,
    dst_ent.name                AS destination_entity,
    dst_acct.country_code       AS destination_country
FROM transactions t
JOIN accounts src_acct ON src_acct.account_id = t.source_account_id
JOIN entities src_ent  ON src_ent.entity_id   = src_acct.entity_id
JOIN accounts dst_acct ON dst_acct.account_id = t.destination_account_id
JOIN entities dst_ent  ON dst_ent.entity_id   = dst_acct.entity_id
WHERE t.status = 'COMPLETED'
  AND (
        src_acct.country_code IN (SELECT country_code FROM high_risk_countries)
     OR dst_acct.country_code IN (SELECT country_code FROM high_risk_countries)
  )
ORDER BY t.transaction_timestamp DESC;


-- ---------------------------------------------------------------------------
-- 5. TRANSACTION CHAIN NETWORK TRAVERSAL (CTE, depth >= 3)
--    Finds chains of money movement across at least 3 hops, starting from
--    recently flagged transactions.
-- ---------------------------------------------------------------------------
WITH RECURSIVE transaction_chain AS (
    -- Anchor: start from flagged transactions
    SELECT
        t.transaction_id                    AS chain_start_id,
        t.transaction_id,
        t.source_account_id,
        t.destination_account_id,
        t.amount,
        t.transaction_timestamp,
        1                                   AS depth,
        ARRAY[t.transaction_id]             AS path,
        t.amount                            AS cumulative_amount
    FROM transactions t
    WHERE t.flagged IS TRUE
      AND t.status  = 'COMPLETED'

    UNION ALL

    -- Recursive: follow money from destination of previous hop
    SELECT
        tc.chain_start_id,
        t_next.transaction_id,
        t_next.source_account_id,
        t_next.destination_account_id,
        t_next.amount,
        t_next.transaction_timestamp,
        tc.depth + 1,
        tc.path || t_next.transaction_id,
        tc.cumulative_amount + t_next.amount
    FROM transaction_chain tc
    JOIN transactions t_next
        ON  t_next.source_account_id   = tc.destination_account_id
        AND t_next.transaction_timestamp > tc.transaction_timestamp
        AND t_next.transaction_timestamp <= tc.transaction_timestamp + INTERVAL '72 hours'
        AND NOT (t_next.transaction_id = ANY(tc.path))  -- prevent cycles
        AND t_next.status = 'COMPLETED'
    WHERE tc.depth < 6   -- maximum traversal depth
)
SELECT
    chain_start_id,
    path,
    depth,
    transaction_id          AS final_hop_txn_id,
    cumulative_amount,
    transaction_timestamp   AS final_hop_timestamp
FROM transaction_chain
WHERE depth >= 3
ORDER BY depth DESC, cumulative_amount DESC;
