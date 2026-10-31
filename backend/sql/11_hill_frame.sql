-- Hillstrom model frame: treatment = any email, target = conversion.
-- Baselines for one-hot columns: suburban zip code, phone channel.
CREATE OR REPLACE TABLE {{P}}_FRAME AS
SELECT
    client_id,
    CAST(CASE WHEN segment = 'No E-Mail' THEN 0 ELSE 1 END AS DECIMAL(1,0))   AS treatment,
    CAST(conversion AS DECIMAL(1,0))                                         AS target,
    CAST(recency AS DOUBLE)                                                  AS recency,
    LN(1 + history)                                                          AS history_log,
    CAST(mens AS DOUBLE)                                                     AS mens,
    CAST(womens AS DOUBLE)                                                   AS womens,
    CAST(newbie AS DOUBLE)                                                   AS newbie,
    CAST(CASE WHEN zip_code = 'Urban' THEN 1 ELSE 0 END AS DOUBLE)           AS zip_urban,
    CAST(CASE WHEN zip_code = 'Rural' THEN 1 ELSE 0 END AS DOUBLE)           AS zip_rural,
    CAST(CASE WHEN channel = 'Web' THEN 1 ELSE 0 END AS DOUBLE)              AS channel_web,
    CAST(CASE WHEN channel = 'Multichannel' THEN 1 ELSE 0 END AS DOUBLE)     AS channel_multi
FROM {{P}}_RAW;
