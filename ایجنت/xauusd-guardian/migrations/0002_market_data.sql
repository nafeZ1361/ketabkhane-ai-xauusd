-- 0002_market_data.sql — Phase 2 market data
-- Additive only. Never edit an applied migration; add a new file instead.

CREATE TABLE IF NOT EXISTS bars (
    symbol        TEXT    NOT NULL,
    timeframe     TEXT    NOT NULL,
    time_utc      TEXT    NOT NULL,
    open          REAL    NOT NULL,
    high          REAL    NOT NULL,
    low           REAL    NOT NULL,
    close         REAL    NOT NULL,
    tick_volume   INTEGER NOT NULL,
    spread_points INTEGER NOT NULL,
    real_volume   REAL    NOT NULL,
    content_sha256 TEXT   NOT NULL,
    first_seen_utc TEXT   NOT NULL,
    last_seen_utc  TEXT   NOT NULL,
    run_id        TEXT    NOT NULL,
    PRIMARY KEY (symbol, timeframe, time_utc)
);

CREATE TABLE IF NOT EXISTS bar_revisions (
    symbol        TEXT NOT NULL,
    timeframe     TEXT NOT NULL,
    time_utc      TEXT NOT NULL,
    seen_utc      TEXT NOT NULL,
    open          REAL NOT NULL,
    high          REAL NOT NULL,
    low           REAL NOT NULL,
    close         REAL NOT NULL,
    tick_volume   INTEGER NOT NULL,
    content_sha256 TEXT NOT NULL,
    run_id        TEXT NOT NULL,
    UNIQUE (symbol, timeframe, time_utc, content_sha256)
);

CREATE TABLE IF NOT EXISTS ticks (
    symbol   TEXT    NOT NULL,
    time_msc INTEGER NOT NULL,
    time_utc TEXT    NOT NULL,
    bid      REAL    NOT NULL,
    ask      REAL    NOT NULL,
    last     REAL    NOT NULL,
    volume   INTEGER NOT NULL,
    flags    INTEGER NOT NULL,
    run_id   TEXT    NOT NULL,
    PRIMARY KEY (symbol, time_msc, bid, ask)
);

CREATE TABLE IF NOT EXISTS feed_runs (
    run_id      TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    timeframe   TEXT,
    started_utc TEXT NOT NULL,
    finished_utc TEXT,
    status      TEXT NOT NULL,
    inserted    INTEGER NOT NULL DEFAULT 0,
    revised     INTEGER NOT NULL DEFAULT 0,
    gaps        INTEGER NOT NULL DEFAULT 0,
    reason      TEXT
);

CREATE TABLE IF NOT EXISTS data_gaps (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    TEXT NOT NULL,
    symbol    TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    gap_start_utc TEXT NOT NULL,
    bars_missing  INTEGER NOT NULL,
    created_utc   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS time_sync (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_utc TEXT NOT NULL,
    status      TEXT NOT NULL,
    offset_ms   REAL,
    mad_ms      REAL,
    samples     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantined_series (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,
    reason      TEXT NOT NULL,
    created_utc TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bars_tf_time ON bars (timeframe, time_utc);
CREATE INDEX IF NOT EXISTS idx_ticks_time ON ticks (time_utc);
CREATE INDEX IF NOT EXISTS idx_runs_started ON feed_runs (started_utc);
