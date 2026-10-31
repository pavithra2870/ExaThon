-- X5 features, computed in Exasol from the purchase history.
-- Reference date = latest transaction in the history. Purchases are line-level, so
-- transaction-level fields (purchase_sum, points) are collapsed per transaction first.

-- 0. Customer buckets. Heavy aggregations over purchases run one bucket at a time
-- (statements containing the bucket marker are repeated for buckets 0..15 by run_script),
-- because the database has only a few GB of RAM.
CREATE OR REPLACE TABLE {{P}}_BUCKET AS
SELECT client_id, MOD(ROW_NUMBER() OVER (ORDER BY client_id), 16) AS b
FROM {{P}}_CLIENTS;

-- 1. One row per transaction.
CREATE OR REPLACE TABLE {{P}}_TX (
    client_id         VARCHAR(16),
    transaction_id    VARCHAR(16),
    ts                TIMESTAMP,
    purchase_sum      DOUBLE,
    regular_received  DOUBLE,
    express_received  DOUBLE,
    regular_spent     DOUBLE,
    express_spent     DOUBLE,
    store_id          VARCHAR(16),
    DISTRIBUTE BY client_id
);

INSERT INTO {{P}}_TX
SELECT
    p.client_id,
    p.transaction_id,
    MAX(p.transaction_datetime),
    MAX(p.purchase_sum),
    MAX(p.regular_points_received),
    MAX(p.express_points_received),
    MAX(ABS(p.regular_points_spent)),
    MAX(ABS(p.express_points_spent)),
    MAX(p.store_id)
FROM {{P}}_PURCHASES p
JOIN {{P}}_BUCKET b ON b.client_id = p.client_id
WHERE b.b = {{BUCKET}}
GROUP BY p.client_id, p.transaction_id;

-- 2. Transaction aggregates per client over 30/90/180 days and all history.
CREATE OR REPLACE TABLE {{P}}_TX_AGG AS
WITH r AS (SELECT MAX(ts) AS ref_date FROM {{P}}_TX)
SELECT
    t.client_id,
    DAYS_BETWEEN(MAX(r.ref_date), MAX(t.ts))                                          AS recency_days,
    SUM(CASE WHEN t.ts > ADD_DAYS(r.ref_date, -30)  THEN 1 ELSE 0 END)                AS tx_30d,
    SUM(CASE WHEN t.ts > ADD_DAYS(r.ref_date, -90)  THEN 1 ELSE 0 END)                AS tx_90d,
    SUM(CASE WHEN t.ts > ADD_DAYS(r.ref_date, -180) THEN 1 ELSE 0 END)                AS tx_180d,
    COUNT(*)                                                                     AS tx_all,
    SUM(CASE WHEN t.ts > ADD_DAYS(r.ref_date, -30)  THEN t.purchase_sum ELSE 0 END)   AS spend_30d,
    SUM(CASE WHEN t.ts > ADD_DAYS(r.ref_date, -90)  THEN t.purchase_sum ELSE 0 END)   AS spend_90d,
    SUM(CASE WHEN t.ts > ADD_DAYS(r.ref_date, -180) THEN t.purchase_sum ELSE 0 END)   AS spend_180d,
    SUM(t.purchase_sum)                                                          AS spend_all,
    AVG(t.purchase_sum)                                                          AS avg_basket,
    COUNT(DISTINCT t.store_id)                                                   AS n_stores,
    SUM(t.regular_received + t.express_received)                                 AS points_received,
    SUM(t.express_received)                                                      AS express_received,
    SUM(t.regular_spent + t.express_spent)                                       AS points_spent
FROM {{P}}_TX t
CROSS JOIN r
GROUP BY t.client_id;

-- 3. Line-level aggregates: product breadth and spend shares (one bucket at a time).
CREATE OR REPLACE TABLE {{P}}_LINE_AGG (
    client_id          VARCHAR(16),
    n_products         DECIMAL(9,0),
    n_level1           DECIMAL(9,0),
    own_brand_share    DOUBLE,
    alcohol_share      DOUBLE,
    points_paid_share  DOUBLE,
    DISTRIBUTE BY client_id
);

INSERT INTO {{P}}_LINE_AGG
SELECT
    p.client_id,
    COUNT(DISTINCT p.product_id),
    COUNT(DISTINCT pr.level_1),
    SUM(CASE WHEN pr.is_own_trademark = 1 THEN p.trn_sum_from_iss ELSE 0 END)
        / NULLIF(SUM(p.trn_sum_from_iss), 0),
    SUM(CASE WHEN pr.is_alcohol = 1 THEN p.trn_sum_from_iss ELSE 0 END)
        / NULLIF(SUM(p.trn_sum_from_iss), 0),
    SUM(COALESCE(p.trn_sum_from_red, 0))
        / NULLIF(SUM(p.trn_sum_from_iss + COALESCE(p.trn_sum_from_red, 0)), 0)
FROM {{P}}_PURCHASES p
JOIN {{P}}_BUCKET b ON b.client_id = p.client_id
LEFT JOIN {{P}}_PRODUCTS pr ON pr.product_id = p.product_id
WHERE b.b = {{BUCKET}}
GROUP BY p.client_id;

-- 4. Frame: labelled customers plus the unlabelled audience (treatment and target NULL).
CREATE OR REPLACE TABLE {{P}}_FRAME AS
WITH base AS (
    SELECT client_id, CAST(treatment_flg AS DECIMAL(1,0)) AS treatment, CAST(target AS DECIMAL(1,0)) AS target
    FROM {{P}}_UPLIFT_TRAIN
    UNION ALL
    SELECT client_id, CAST(NULL AS DECIMAL(1,0)), CAST(NULL AS DECIMAL(1,0))
    FROM {{P}}_UPLIFT_TEST
),
r AS (SELECT MAX(ts) AS ref_date FROM {{P}}_TX)
SELECT
    b.client_id,
    b.treatment,
    b.target,
    CAST(a.recency_days AS DOUBLE)                                                AS recency_days,
    LN(1 + COALESCE(a.tx_30d, 0))                                                 AS tx_30d_log,
    LN(1 + COALESCE(a.tx_90d, 0))                                                 AS tx_90d_log,
    LN(1 + COALESCE(a.tx_180d, 0))                                                AS tx_180d_log,
    LN(1 + COALESCE(a.tx_all, 0))                                                 AS tx_all_log,
    LN(1 + GREATEST(COALESCE(a.spend_30d, 0), 0))                                 AS spend_30d_log,
    LN(1 + GREATEST(COALESCE(a.spend_90d, 0), 0))                                 AS spend_90d_log,
    LN(1 + GREATEST(COALESCE(a.spend_180d, 0), 0))                                AS spend_180d_log,
    LN(1 + GREATEST(COALESCE(a.spend_all, 0), 0))                                 AS spend_all_log,
    LN(1 + GREATEST(a.avg_basket, 0))                                             AS avg_basket_log,
    CAST(COALESCE(a.n_stores, 0) AS DOUBLE)                                       AS n_stores,
    LN(1 + COALESCE(l.n_products, 0))                                             AS n_products_log,
    CAST(COALESCE(l.n_level1, 0) AS DOUBLE)                                       AS n_level1,
    l.own_brand_share,
    l.alcohol_share,
    LN(1 + GREATEST(COALESCE(a.points_received, 0), 0))                           AS points_received_log,
    LN(1 + GREATEST(COALESCE(a.points_spent, 0), 0))                              AS points_spent_log,
    l.points_paid_share,
    a.express_received / NULLIF(a.points_received, 0)                             AS express_share,
    CAST(DAYS_BETWEEN(r.ref_date, c.first_issue_date) AS DOUBLE)                       AS tenure_days,
    CAST(CASE WHEN c.first_redeem_date <= r.ref_date THEN 1 ELSE 0 END AS DOUBLE)      AS redeemed,
    CAST(CASE WHEN c.age BETWEEN 14 AND 100 THEN c.age END AS DOUBLE)             AS age,
    CAST(CASE WHEN c.age BETWEEN 14 AND 100 THEN 0 ELSE 1 END AS DOUBLE)          AS age_missing,
    CAST(CASE WHEN c.gender = 'F' THEN 1 ELSE 0 END AS DOUBLE)                    AS gender_f,
    CAST(CASE WHEN c.gender = 'M' THEN 1 ELSE 0 END AS DOUBLE)                    AS gender_m
FROM base b
CROSS JOIN r
LEFT JOIN {{P}}_CLIENTS  c ON c.client_id = b.client_id
LEFT JOIN {{P}}_TX_AGG   a ON a.client_id = b.client_id
LEFT JOIN {{P}}_LINE_AGG l ON l.client_id = b.client_id;
