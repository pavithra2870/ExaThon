-- Deterministic train / holdout split by hash of client_id (salted).
-- bucket = first 4 hex digits of SHA1 as a fraction in [0, 1). Rows without a
-- treatment label are the unlabelled audience: scored for the customer list, never evaluated.
CREATE OR REPLACE TABLE {{P}}_SPLIT AS
SELECT
    client_id,
    CASE WHEN treatment IS NULL THEN 'audience'
         WHEN bucket < {{HOLDOUT}} THEN 'holdout'
         ELSE 'train' END AS part,
    bucket
FROM (
    SELECT
        client_id,
        treatment,
        ( (INSTR('0123456789abcdef', SUBSTR(h, 1, 1)) - 1) * 4096
        + (INSTR('0123456789abcdef', SUBSTR(h, 2, 1)) - 1) * 256
        + (INSTR('0123456789abcdef', SUBSTR(h, 3, 1)) - 1) * 16
        + (INSTR('0123456789abcdef', SUBSTR(h, 4, 1)) - 1) ) / 65536.0 AS bucket
    FROM (
        SELECT client_id, treatment, LOWER(HASH_SHA1('promolens-split:' || client_id)) AS h
        FROM {{P}}_FRAME
    ) hashed
) bucketed;
