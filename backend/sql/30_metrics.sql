-- Named metric queries used by the API and `pipeline.evaluate`. Not run by run_sql.
-- Each block starts with "-- name: <id>". {{P}} is the dataset prefix; {name} values are
-- bound by pyexasol at run time. query_id = sha1 of the rendered text before binding.
--
-- All evaluation uses the 30% holdout only. Strategies:
--   uplift         rank by estimated p1 - p0
--   likely_buyers  rank by estimated p1
--   random         expected result of contacting k% at random = whole-holdout effect
-- At top k% contacted: per_1000 = (Yt/Nt - Yc/Nc) * 1000, extra outcomes per 1,000 contacted.
-- share_anyway = mean model p0 of those contacted (an estimate).
-- qini = (Yt - Yc * Nt / Nc) / N, cumulative extra outcomes as a share of the holdout.

-- name: _curve_ctes
h AS (
    SELECT client_id, treatment, target, p0, p1, uplift, grp,
           HASH_SHA1('promolens-tiebreak:' || client_id) AS tb
    FROM {{P}}_SCORES
    WHERE part = 'holdout'
),
tot AS (
    SELECT COUNT(*)                        AS n,
           SUM(treatment)                  AS nt,
           SUM(treatment * target)         AS yt,
           SUM(1 - treatment)              AS nc,
           SUM((1 - treatment) * target)   AS yc,
           AVG(p0)                         AS mean_p0
    FROM h
),
ranked AS (
    SELECT 'uplift' AS strategy, treatment, target, p0, grp,
           ROW_NUMBER() OVER (ORDER BY uplift DESC, tb) AS rn
    FROM h
    UNION ALL
    SELECT 'likely_buyers' AS strategy, treatment, target, p0, grp,
           ROW_NUMBER() OVER (ORDER BY p1 DESC, tb) AS rn
    FROM h
),
pct AS (
    SELECT r.strategy,
           CEIL(r.rn * 100.0 / t.n)                              AS k,
           COUNT(*)                                              AS nn,
           SUM(r.treatment)                                      AS nt,
           SUM(r.treatment * r.target)                           AS yt,
           SUM(1 - r.treatment)                                  AS nc,
           SUM((1 - r.treatment) * r.target)                     AS yc,
           SUM(r.p0)                                             AS sp0,
           SUM(CASE WHEN r.grp = 'tipped'  THEN 1 ELSE 0 END)    AS g_tipped,
           SUM(CASE WHEN r.grp = 'anyway'  THEN 1 ELSE 0 END)    AS g_anyway,
           SUM(CASE WHEN r.grp = 'never'   THEN 1 ELSE 0 END)    AS g_never,
           SUM(CASE WHEN r.grp = 'put_off' THEN 1 ELSE 0 END)    AS g_put_off
    FROM ranked r
    CROSS JOIN tot t
    GROUP BY r.strategy, CEIL(r.rn * 100.0 / t.n)
),
cum AS (
    SELECT strategy, k,
           SUM(nn)        OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS n_k,
           SUM(nt)        OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS nt_k,
           SUM(yt)        OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS yt_k,
           SUM(nc)        OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS nc_k,
           SUM(yc)        OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS yc_k,
           SUM(sp0)       OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS sp0_k,
           SUM(g_tipped)  OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS g_tipped_k,
           SUM(g_anyway)  OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS g_anyway_k,
           SUM(g_never)   OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS g_never_k,
           SUM(g_put_off) OVER (PARTITION BY strategy ORDER BY k ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS g_put_off_k
    FROM pct
),
curve AS (
    SELECT c.strategy,
           CAST(c.k AS DECIMAL(4,0))                                                        AS k,
           c.n_k, c.nt_k, c.yt_k, c.nc_k, c.yc_k,
           CASE WHEN c.nt_k > 0 AND c.nc_k > 0
                THEN (CAST(c.yt_k AS DOUBLE) / c.nt_k - CAST(c.yc_k AS DOUBLE) / c.nc_k) * 1000 END AS per_1000,
           CASE WHEN c.nc_k > 0
                THEN (c.yt_k - CAST(c.yc_k AS DOUBLE) * c.nt_k / c.nc_k) / t.n END           AS qini,
           CAST(c.sp0_k AS DOUBLE) / c.n_k                                                  AS share_anyway,
           c.g_tipped_k, c.g_anyway_k, c.g_never_k, c.g_put_off_k
    FROM cum c
    CROSS JOIN tot t
    UNION ALL
    SELECT 'random'                                                                         AS strategy,
           CAST(ks.k AS DECIMAL(4,0))                                                       AS k,
           ROUND(ks.k * t.n / 100.0), NULL, NULL, NULL, NULL,
           (CAST(t.yt AS DOUBLE) / t.nt - CAST(t.yc AS DOUBLE) / t.nc) * 1000               AS per_1000,
           ks.k / 100.0 * (t.yt - CAST(t.yc AS DOUBLE) * t.nt / t.nc) / t.n                 AS qini,
           t.mean_p0                                                                        AS share_anyway,
           NULL, NULL, NULL, NULL
    FROM (SELECT DISTINCT k FROM pct) ks
    CROSS JOIN tot t
),
curve_b AS (
    SELECT c.*, b.lo, b.hi
    FROM curve c
    LEFT JOIN {{P}}_BOOTSTRAP b
           ON b.strategy = c.strategy AND b.k = c.k AND b.metric = 'per_1000'
)

-- name: curve
WITH {{CURVE_CTES}}
SELECT * FROM curve_b
ORDER BY strategy, k

-- name: overview
WITH {{CURVE_CTES}}
SELECT * FROM curve_b
WHERE k = {budget}
ORDER BY strategy

-- name: summary
SELECT part,
       COUNT(*)                                                    AS n,
       SUM(treatment)                                              AS nt,
       SUM(1 - treatment)                                          AS nc,
       CAST(SUM(treatment * target) AS DOUBLE) / NULLIF(SUM(treatment), 0)           AS treated_rate,
       CAST(SUM((1 - treatment) * target) AS DOUBLE) / NULLIF(SUM(1 - treatment), 0) AS control_rate,
       AVG(p0)                                                     AS mean_p0,
       AVG(uplift)                                                 AS mean_uplift
FROM {{P}}_SCORES
GROUP BY part
ORDER BY part

-- name: proof
WITH {{CURVE_CTES}},
at_k AS (SELECT * FROM curve WHERE k = {budget})
SELECT 'likely_buyers' AS versus, u.per_1000 - o.per_1000 AS diff_per_1000, b.lo, b.hi
FROM at_k u
JOIN at_k o ON u.strategy = 'uplift' AND o.strategy = 'likely_buyers'
LEFT JOIN {{P}}_BOOTSTRAP b ON b.strategy = 'uplift' AND b.metric = 'diff_buyers' AND b.k = {budget}
UNION ALL
SELECT 'random' AS versus, u.per_1000 - o.per_1000 AS diff_per_1000, b.lo, b.hi
FROM at_k u
JOIN at_k o ON u.strategy = 'uplift' AND o.strategy = 'random'
LEFT JOIN {{P}}_BOOTSTRAP b ON b.strategy = 'uplift' AND b.metric = 'diff_random' AND b.k = {budget}

-- name: qini
WITH {{CURVE_CTES}},
last_k AS (SELECT strategy, qini AS q100 FROM curve WHERE k = 100)
SELECT c.strategy,
       AVG(c.qini - c.k / 100.0 * l.q100) AS qini_coefficient,
       MAX(l.q100)                         AS qini_at_100
FROM curve c
JOIN last_k l ON l.strategy = c.strategy
GROUP BY c.strategy
ORDER BY c.strategy

-- name: deciles
WITH h AS (
    SELECT treatment, target, p0, p1, uplift,
           HASH_SHA1('promolens-tiebreak:' || client_id) AS tb
    FROM {{P}}_SCORES
    WHERE part = 'holdout'
),
d AS (
    SELECT h.*, NTILE(10) OVER (ORDER BY uplift DESC, tb) AS decile
    FROM h
),
agg AS (
    SELECT decile,
           COUNT(*)                          AS n,
           SUM(treatment)                    AS nt,
           SUM(1 - treatment)                AS nc,
           SUM(treatment * target)           AS yt,
           SUM((1 - treatment) * target)     AS yc,
           AVG(uplift)                       AS predicted_uplift,
           AVG(p0)                           AS mean_p0,
           AVG(p1)                           AS mean_p1
    FROM d
    GROUP BY decile
)
SELECT a.*,
       CAST(a.yt AS DOUBLE) / NULLIF(a.nt, 0)                                         AS treated_rate,
       CAST(a.yc AS DOUBLE) / NULLIF(a.nc, 0)                                         AS control_rate,
       CAST(a.yt AS DOUBLE) / NULLIF(a.nt, 0) - CAST(a.yc AS DOUBLE) / NULLIF(a.nc, 0) AS observed_uplift,
       b.lo, b.hi
FROM agg a
LEFT JOIN {{P}}_BOOTSTRAP b ON b.strategy = 'uplift' AND b.metric = 'decile_uplift' AND b.k = a.decile
ORDER BY a.decile

-- name: groups
WITH s AS (SELECT * FROM {{P}}_SCORES),
tot AS (SELECT COUNT(*) AS n FROM s),
g AS (
    SELECT s.grp,
           COUNT(*)                                                                    AS n,
           AVG(s.p0)                                                                   AS mean_p0,
           AVG(s.p1)                                                                   AS mean_p1,
           AVG(s.uplift)                                                               AS mean_uplift,
           SUM(CASE WHEN s.part = 'holdout' AND s.treatment = 1 THEN 1 ELSE 0 END)        AS holdout_nt,
           SUM(CASE WHEN s.part = 'holdout' AND s.treatment = 1 THEN s.target ELSE 0 END) AS holdout_yt,
           SUM(CASE WHEN s.part = 'holdout' AND s.treatment = 0 THEN 1 ELSE 0 END)        AS holdout_nc,
           SUM(CASE WHEN s.part = 'holdout' AND s.treatment = 0 THEN s.target ELSE 0 END) AS holdout_yc
    FROM s
    GROUP BY s.grp
)
SELECT g.*,
       CAST(g.n AS DOUBLE) / t.n                               AS share,
       CAST(g.holdout_yt AS DOUBLE) / NULLIF(g.holdout_nt, 0)  AS holdout_treated_rate,
       CAST(g.holdout_yc AS DOUBLE) / NULLIF(g.holdout_nc, 0)  AS holdout_control_rate
FROM g
CROSS JOIN tot t
ORDER BY g.grp

-- name: customers
SELECT client_id, part, p0, p1, uplift, grp, COUNT(*) OVER () AS total_rows
FROM {{P}}_SCORES
WHERE {grp} IS NULL OR grp = {grp}
ORDER BY {order_by!r}
LIMIT {limit!d} OFFSET {offset!d}

-- name: reasons
SELECT client_id, feature, fvalue, z, contrib
FROM (
    SELECT z.client_id, z.feature, z.fvalue, z.z,
           z.z * (z.coef_treated * s.p1 * (1 - s.p1) - z.coef_control * s.p0 * (1 - s.p0)) AS contrib
    FROM {{P}}_Z_V z
    JOIN {{P}}_SCORES s ON s.client_id = z.client_id
    WHERE z.client_id IN ({ids!r})
) x
QUALIFY ROW_NUMBER() OVER (PARTITION BY client_id ORDER BY ABS(contrib) DESC) <= 3
ORDER BY client_id, ABS(contrib) DESC

-- name: health_tables
SELECT TABLE_NAME AS table_name, TABLE_ROW_COUNT AS row_count
FROM EXA_ALL_TABLES
WHERE TABLE_SCHEMA = '{{SCHEMA}}'
ORDER BY TABLE_NAME
