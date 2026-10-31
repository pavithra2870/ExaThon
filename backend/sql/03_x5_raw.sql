-- X5 RetailHero raw tables, typed before import. Column order matches the CSV headers.
CREATE OR REPLACE TABLE {{P}}_CLIENTS (
    client_id          VARCHAR(16) NOT NULL,
    first_issue_date   TIMESTAMP,
    first_redeem_date  TIMESTAMP,
    age                DECIMAL(6,0),
    gender             CHAR(1)
);

CREATE OR REPLACE TABLE {{P}}_PRODUCTS (
    product_id        VARCHAR(16) NOT NULL,
    level_1           VARCHAR(16),
    level_2           VARCHAR(16),
    level_3           VARCHAR(16),
    level_4           VARCHAR(16),
    segment_id        DOUBLE,
    brand_id          VARCHAR(16),
    vendor_id         VARCHAR(16),
    netto             DOUBLE,
    is_own_trademark  DECIMAL(1,0),
    is_alcohol        DECIMAL(1,0)
);

CREATE OR REPLACE TABLE {{P}}_PURCHASES (
    client_id                VARCHAR(16) NOT NULL,
    transaction_id           VARCHAR(16),
    transaction_datetime     TIMESTAMP,
    regular_points_received  DOUBLE,
    express_points_received  DOUBLE,
    regular_points_spent     DOUBLE,
    express_points_spent     DOUBLE,
    purchase_sum             DOUBLE,
    store_id                 VARCHAR(16),
    product_id               VARCHAR(16),
    product_quantity         DOUBLE,
    trn_sum_from_iss         DOUBLE,
    trn_sum_from_red         DOUBLE,
    DISTRIBUTE BY client_id
);

CREATE OR REPLACE TABLE {{P}}_UPLIFT_TRAIN (
    client_id      VARCHAR(16) NOT NULL,
    treatment_flg  DECIMAL(1,0),
    target         DECIMAL(1,0)
);

CREATE OR REPLACE TABLE {{P}}_UPLIFT_TEST (
    client_id  VARCHAR(16) NOT NULL
);
