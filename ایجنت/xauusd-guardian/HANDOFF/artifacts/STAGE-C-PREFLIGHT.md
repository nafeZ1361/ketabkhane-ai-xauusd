# Stage C — Preflight (read-only)

UTC 2026-11-17 16:15 · Asia/Tehran 19:45 (UTC+03:30)

## 1. Stage B preserved

| Item | Value |
|---|---|
| Repository | `nafeZ1361/ketabkhane-ai-xauusd` |
| Branch | `fix/w1-timezone-validation` |
| HEAD | `c192c16c2df89f05327cc6512b728cb0ba9af134` (unchanged since Stage A) |
| Worktree | 2 modified, 2 untracked — all Stage A/B |
| Stage B verdict | independent `PASS` (timezone reinspection) |

```
 M ایجنت/xauusd-guardian/DECISIONS_LOG.md
 M ایجنت/xauusd-guardian/scripts/research_edge.py
?? ایجنت/xauusd-guardian/HANDOFF/artifacts/STAGE-A-AUDIT.md
?? ایجنت/xauusd-guardian/tests/unit/test_stageB_leakage.py
```

`git diff --stat`: `DECISIONS_LOG.md` +5, `research_edge.py` +75/−6. Nothing outside
`ایجنت/xauusd-guardian/`. No unrelated change, no commit, no push.

## 2. BOM check

Read the raw bytes of the committed blob and of the working file:

```
git cat-file blob HEAD:.../scripts/research_edge.py   first 3 bytes = 22 22 22  (""")
worktree   .../scripts/research_edge.py               first 3 bytes = 22 22 22
```

**No UTF-8 BOM, before or after Stage B.** (An earlier check appeared to show `EF BB BF`;
that was a PowerShell redirection artefact — the file was UTF-16 encoded by `>` on the way
out. Re-checked via `git cat-file` bytes.) No encoding change was made; nothing to record
in `DECISIONS_LOG.md` beyond this note.

## 3. Spread data audit (read-only)

| Property | Finding | Evidence |
|---|---|---|
| Dataset | `C:\Users\icFixer.ir\Desktop\کتابخونه بخش طلایی\XAUUSD_M1_201610030100_202610092354.csv` | 205 MB, MT5 TSV |
| Columns | `DATE, TIME, OPEN, HIGH, LOW, CLOSE, TICKVOL, VOL, SPREAD` | header |
| SPREAD available | yes, integer per bar | sample `[38, 39, 47, 40, 49]` |
| Distribution (whole file, n=3,489,359) | min 0 · p05 18 · **median 30** · p95 50 · max 2005 · zero-share 1.6e-05 | measured over every row |
| `SYMBOL_POINT` / `DIGITS` / `TICK_SIZE` | `tick_size = 0.01`, `digits = 2` declared in `configs/config.toml` (broker expectations), `max_spread_points = 30` | config lines 28-29, 35 |
| Spread units | **points**, 1 point = 0.01 USD → median 30 = $0.30 | inferred from `tick_size=0.01`, not from a live `symbol_info` |
| Snapshot or average? | **UNKNOWN** — MT5 records one spread value per bar; the file cannot tell open-snapshot vs average | no metadata |
| Timestamp alignment | bar timestamps are MT5 **server** time (UTC+2/+3), not UTC | D-013 / Stage B |
| Bid/Ask | **not available** — OHLC only, no quote columns | header |

Note: `max_spread_points = 30` in config is a *gate threshold* for collection, not a
property of this file — observed spread reaches 2005 points, so the file spans
periods outside that gate.

Sampling: the first version of this table was computed from the **first 300,000 rows**
(2016-10 to 2017-09) and was not representative. The figures above cover the entire
file; the earlier head-sample values (median 28, p95 39, max 483) are withdrawn.

## 4. Commission and slippage

Neither is present in the dataset, the config, or any repository artifact (grep for
`commission|slippage|swap|fee` in `configs/config.toml` returns nothing).

Therefore:

- **Spread-only accounting** is possible and may proceed.
- **Full transaction-cost / full-net claims are `BLOCKED`** until commission and slippage
  are supported by evidence. No value will be invented.

## 5. Inspector availability

An independent inspector is available and has already served Stages A and B (separate
session, read-only, own repros). It can access the repository, diffs, test execution, the
source dataset and its own spread calculations. **Not blocked.**

## 6. Preflight verdict and open blockers

**PASS for preflight.** Stage B is safe to preserve and isolate: the change set is confined
to four paths, all Stage A/B, and no unrelated edit exists.

Open blockers for Stage C itself:

| # | Blocker | Effect |
|---|---|---|
| C-B1 | commission unknown | full-net claims blocked; spread-only net allowed |
| C-B2 | slippage unknown | same |
| C-B3 | spread semantics (snapshot vs average) unverified | a cost model must state it as an assumption |
| C-B4 | point size taken from config, not from live `symbol_info` | conversion is supported, not verified |

No source, data, evidence or manifest file was modified. No commit, no push, no cleanup.
Stage C1 not started.
