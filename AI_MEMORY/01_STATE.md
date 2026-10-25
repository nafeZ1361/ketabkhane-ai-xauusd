# AI_MEMORY/01_STATE — وضعیت فشرده

- محیط: `EXEC_ENV_AVAILABLE`
- فاز: A2 — رابط کاربری متوقف؛ اولویت A2.5
- استراتژی: `ma_100_400` + فیلتر ۵۰۰ → **DEFERRED (بدون OOS معتبر)**
- هزینه: اسپرد ۳۰ + اسلیپیج ۲ point + سواپ ۰٫۰۱٪/شب (PROVISIONAL)
- تست: ۱۱۴ آزمون سبز (A2.5 کامل)، پوشش ~۹۵٪
- UI: A2.1 و A2.2 پیاده (A2.2 طبق نسخهٔ ۲.۰ باید پس از A2.5 باشد — DEC-2026-024)
- موانع: `ISSUE-2026-0010` (DEFERRED)، ۰۰۰۲/۰۰۰۶/۰۰۰۷ باز، ۰۰۰۳ `LEGAL_HOLD`

## گام بعد
اجرای A3 روی دیتاست محلی: `python scripts/a3_grid.py --csv data/XAUUSD_M1_*.csv --profile config/broker_profile.json` و `scripts/a3_breakout.py`؛ سپس `python -m validation.gates --ledger artifacts/ledger/experiments.jsonl --out artifacts/gates_report.json` و شاهد در `docs/evidence/a3_grid_report.md`.
