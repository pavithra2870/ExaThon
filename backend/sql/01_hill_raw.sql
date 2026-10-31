-- Hillstrom raw table, typed before import. client_id is generated from the row number
-- at load time (the source has no id). The spend column is not loaded: PromoLens
-- reports counts and rates only.
CREATE OR REPLACE TABLE {{P}}_RAW (
    client_id   VARCHAR(16) NOT NULL,
    recency     DECIMAL(4,0),
    history     DOUBLE,
    mens        DECIMAL(1,0),
    womens      DECIMAL(1,0),
    zip_code    VARCHAR(16),
    newbie      DECIMAL(1,0),
    channel     VARCHAR(16),
    segment     VARCHAR(20),
    visit       DECIMAL(1,0),
    conversion  DECIMAL(1,0)
);
