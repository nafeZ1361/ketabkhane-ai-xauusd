-- Reverse of 0003_signals.sql. Since option 3 (F1) no code executes this file:
-- guardian.storage.db.emit_reverse_sql validates it and returns the SQL for a human
-- to review and run; revert_migration refuses.
--
-- Plain DROP, not DROP TABLE IF EXISTS: a missing table means the live schema
-- drifted from the ledger, and a loud failure is safer than recording a
-- reversal that did not actually happen.
--
-- The dotted filename cannot match the forward discovery pattern
-- ^[0-9]{4}_[a-z0-9_]+\.sql$, so this file can never be applied as the next
-- forward migration even if it were moved into migrations/.

DROP TABLE signals;
DROP TABLE signal_runs;
