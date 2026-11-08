# Phase 2 recheck
F1 OPEN — 20:30–21:30Z request reached terminal at 17:00Z (−12600 s = host +3:30); 200k limit ran out at 21:03:36Z (26.5 min lost), run still OK. int(epoch)+offset lands +0.05 s. estimate_server_offset rejects fresh server-clock ticks (age −6264 s): every run clock_unverified→DEGRADED.
F2 CLOSED — missing bar each side of closure → gaps=2 (1+1); 3+3 → 2×3; intra-session → 1×3; complete → 0.
Suite: 161 passed, 0 failed, 0 skipped, 17.6 s.
Safety: no order_*/positions_*/orders_*/history_* calls; account_info only mt5_readonly.py:138 (identity fields).
Verdict: CHANGES REQUIRED