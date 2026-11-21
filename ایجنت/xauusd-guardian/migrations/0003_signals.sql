-- 0003_signals.sql — Phase 3 signal layer (S5)
-- Additive only. Never edit an applied migration; add a new file instead.
--
-- Reverse (S6) is `migrations/rollback/0003_signals.down.sql`. Its dotted name keeps it
-- out of forward discovery, so it is never applied as a forward step. Since option 3
-- (F1) no code executes it: emit_reverse_sql validates it and returns the SQL a human
-- must review and run.

CREATE TABLE IF NOT EXISTS signal_runs (
    run_id      TEXT    PRIMARY KEY,
    symbol      TEXT    NOT NULL,
    strategy_id TEXT    NOT NULL,
    timeframe   TEXT    NOT NULL,
    from_utc    TEXT    NOT NULL,
    to_utc      TEXT    NOT NULL,
    bars_seen   INTEGER NOT NULL,
    signals     INTEGER NOT NULL,
    written     INTEGER NOT NULL,
    identical   INTEGER NOT NULL,
    status      TEXT    NOT NULL,
    created_utc TEXT    NOT NULL
);

-- `strength` is TEXT, not REAL: the contract requires a finite Decimal and a
-- REAL column would round-trip through binary floating point, changing the
-- deterministic digest. Bars are REAL because they arrive from MT5 as floats;
-- signals are computed and must stay exact.
CREATE TABLE IF NOT EXISTS signals (
    symbol       TEXT NOT NULL,
    timeframe    TEXT NOT NULL,
    bar_time_utc TEXT NOT NULL,
    strategy_id  TEXT NOT NULL,
    direction    TEXT NOT NULL,
    strength     TEXT NOT NULL,
    reason_code  TEXT NOT NULL,
    run_id       TEXT NOT NULL,
    created_utc  TEXT NOT NULL,
    PRIMARY KEY (symbol, timeframe, bar_time_utc, strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_signals_run ON signals (run_id);
CREATE INDEX IF NOT EXISTS idx_signal_runs_window ON signal_runs (strategy_id, timeframe, from_utc);
