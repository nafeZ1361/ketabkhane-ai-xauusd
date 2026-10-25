# DECISIONS_LOG.md

| # | Date | Finding | Decision | Reason |
|---|---|---|---|---|
| 1 | 2026-10-09 | F-005 scope | A | update bot.ipynb (2 lines) |
| 2 | 2026-10-09 | Git workflow | A | authorize dedicated branch + atomic commits (no push/merge without confirmation) |
| 3 | 2026-10-09 | F-005 | A | permit `python -c "import module.mt5"` only; direct run still forbidden |
| 4 | 2026-10-09 | Stage 7.1 closure | A | approve Stage 7.1 Technical Closure |
| 5 | 2026-10-09 | Push/PR | A | push branch + open PR; NO merge; merge gated on bot.ipynb smoke-check |
| 6 | 2026-10-09 | bot.ipynb smoke-check | — | Human performs manually |
| 7 | 2026-10-09 | Stage 7.3 audit | — | start read-only governance audit |
| 8 | 2026-10-09 | F-006 | A | document as GAP only; no code change; defer to Stage 8 |
| 9 | 2026-10-09 | F-004 | B | FIX NOW — config.py single source + execution.py:53 → from_env() |
| 10 | 2026-10-09 | GAP location | A | new stage7/GAPS.md |
| 11 | 2026-10-26 | Stage 8 GAP-005/006/007 | A | implement Monte Carlo + parameter landscape on dedicated branch; frozen run1 untouched; evidence committed |
| 12 | 2026-10-26 | MC verdict interpretation | A | P(positive)=0.0 ⇒ no-edge (not bad luck); hold paper/live block |
| 13 | 2026-10-26 | thr-0.60 positive cells | A | NOT a claim of edge — selection bias on same holdout; requires fresh out-of-sample test before any adoption |
