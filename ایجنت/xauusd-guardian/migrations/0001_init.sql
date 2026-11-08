-- 0001_init.sql — Phase 1 baseline schema
-- Additive only. Never edit an applied migration; add a new file instead.

CREATE TABLE IF NOT EXISTS symbol_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_utc   TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    symbol         TEXT NOT NULL,
    path           TEXT,
    description    TEXT,
    trade_mode     INTEGER NOT NULL,
    digits         INTEGER NOT NULL,
    point          REAL NOT NULL,
    tick_size      REAL NOT NULL,
    tick_value     REAL NOT NULL,
    contract_size  REAL NOT NULL,
    volume_min     REAL NOT NULL,
    volume_max     REAL NOT NULL,
    volume_step    REAL NOT NULL,
    stops_level    INTEGER NOT NULL,
    freeze_level   INTEGER NOT NULL,
    filling_mode   INTEGER NOT NULL,
    currency_base  TEXT,
    currency_profit TEXT,
    visible        INTEGER NOT NULL,
    spec_sha256    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_symbol_snapshots_symbol
    ON symbol_snapshots (symbol, captured_utc);

CREATE TABLE IF NOT EXISTS risk_decisions (
    decision_id       TEXT PRIMARY KEY,
    created_utc       TEXT NOT NULL,
    run_id            TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    status            TEXT NOT NULL,
    volume            REAL NOT NULL,
    target_risk_pct   REAL NOT NULL,
    effective_risk_pct REAL NOT NULL,
    reason            TEXT,
    payload_sha256    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc TEXT NOT NULL,
    run_id      TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL,
    message     TEXT NOT NULL,
    payload     TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_events_run ON audit_events (run_id, created_utc);
