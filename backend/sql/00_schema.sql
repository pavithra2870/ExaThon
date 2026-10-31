-- Schema and shared tables. Idempotent.
CREATE SCHEMA IF NOT EXISTS {{SCHEMA}};

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.QUERY_LOG (
    query_id    CHAR(40),
    dataset     VARCHAR(20),
    metric      VARCHAR(40),
    sql_text    VARCHAR(2000000),
    elapsed_ms  DOUBLE,
    row_count   DECIMAL(18,0),
    session_id  VARCHAR(40),
    logged_at   TIMESTAMP
);
