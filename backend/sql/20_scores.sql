-- Scoring inside Exasol. Requires {{P}}_MODEL_COEF, written by `python -m pipeline.train`.
-- One row per feature: coef_treated, coef_control, mean_value, std_value, fill_value,
-- plus a row '__intercept__' holding the two intercepts.
--
-- z      = (COALESCE(x, fill) - mean) / std
-- p1     = 1 / (1 + EXP(-(b0_treated + SUM(z * coef_treated))))
-- p0     = 1 / (1 + EXP(-(b0_control + SUM(z * coef_control))))
-- uplift = p1 - p0

-- Long format (client, feature, value) keeps scoring and explanations generic.
CREATE OR REPLACE TABLE {{P}}_FEATURES_LONG AS
{{FEATURE_UNPIVOT}};

CREATE OR REPLACE VIEW {{P}}_Z_V AS
SELECT
    l.client_id,
    l.feature,
    l.fvalue,
    (COALESCE(l.fvalue, m.fill_value) - m.mean_value) / m.std_value AS z,
    m.coef_treated,
    m.coef_control
FROM {{P}}_FEATURES_LONG l
JOIN {{P}}_MODEL_COEF m ON m.feature = l.feature;

-- Estimated groups use the thresholds from the dataset config (u = {{U}}, p0 cut = {{P0_CUT}}).
CREATE OR REPLACE VIEW {{P}}_SCORES_V AS
SELECT
    f.client_id,
    s.part,
    f.treatment,
    f.target,
    sc.p0,
    sc.p1,
    sc.p1 - sc.p0 AS uplift,
    CASE WHEN sc.p1 - sc.p0 >= {{U}}  THEN 'tipped'
         WHEN sc.p1 - sc.p0 <= -{{U}} THEN 'put_off'
         WHEN sc.p0 >= {{P0_CUT}}     THEN 'anyway'
         ELSE 'never' END AS grp
FROM (
    SELECT
        lin.client_id,
        1 / (1 + EXP(-(i.coef_control + lin.eta_control))) AS p0,
        1 / (1 + EXP(-(i.coef_treated + lin.eta_treated))) AS p1
    FROM (
        SELECT client_id, SUM(z * coef_treated) AS eta_treated, SUM(z * coef_control) AS eta_control
        FROM {{P}}_Z_V
        GROUP BY client_id
    ) lin
    CROSS JOIN (
        SELECT coef_treated, coef_control FROM {{P}}_MODEL_COEF WHERE feature = '__intercept__'
    ) i
) sc
JOIN {{P}}_FRAME f ON f.client_id = sc.client_id
JOIN {{P}}_SPLIT s ON s.client_id = sc.client_id;

-- Materialise scores for fast metric queries.
CREATE OR REPLACE TABLE {{P}}_SCORES AS
SELECT * FROM {{P}}_SCORES_V;

-- New scores invalidate old bootstrap bands; `pipeline.bootstrap` refills this table.
CREATE OR REPLACE TABLE {{P}}_BOOTSTRAP (
    strategy   VARCHAR(20),
    metric     VARCHAR(20),
    k          DECIMAL(4,0),
    lo         DOUBLE,
    hi         DOUBLE,
    resamples  DECIMAL(6,0),
    seed       DECIMAL(12,0)
);
