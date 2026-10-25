# AI_MEMORY/02_LEDGER — دفتر کار

وضعیت‌ها: DONE / IN_PROGRESS / BLOCKED / NOT_STARTED. هر مورد DONE باید شاهد داشته باشد.

| # | کار | وضعیت | شاهد |
|---|---|---|---|
| 1 | MVP-1: schema/validation/strategies/backtest/report | DONE | src/xauusd_research, tests |
| 2 | بارگذار TSV + timezone (eu-dst) | DONE | tests/test_tsv.py, tests/test_timezones.py |
| 3 | موتور جریانی + هم‌ارزی | DONE | docs/evidence/full_dataset_run.md |
| 4 | مدل هزینهٔ بروکر (اسپرد/اسلیپیج/سواپ) | DONE | docs/evidence/cost_modeling.md |
| 5 | حساسیت اسپرد و رد MA 5/20 | DONE | docs/evidence/spread_sensitivity.md |
| 6 | سه تلاش استراتژی و انتخاب نامزد | DONE | docs/evidence/strategy_attempts.md |
| 7 | OOS 2008–2015 | BLOCKED (داده D1 بود) | out_of_sample_validation_2008_2015.md |
| 8 | Sanity 2024–2026 | DONE (درون‌نمونه‌ای) | sanity_check_2024_2026.md |
| 9 | UI A2.1 | DONE | a2_1_ui_skeleton.md |
| 10 | UI A2.2 | DONE (ولی طبق v2.0 باید پس از A2.5 باشد) | a2_2_run_form.md |
| 11 | A2.5 اعتبارسنجی آماری | DONE | ledger.py + metrics.py + gates CLI + AT-STAT-01..06؛ ۱۱۴ آزمون سبز (DEC-2026-028) |
| 12 | ADL.md | DONE | docs/ADL.md |
| 13 | سند مادر ۲.۰ + AI_MEMORY | DONE | PROJECT_CHARTER_V3.md, AI_MEMORY |
| 14 | سند سبک کار مخزن | DONE | docs/WORKING_STYLE.md |
| 15 | runner خانواده دوم (Donchian) برای M≥2 | DONE | scripts/a3_breakout.py + test end-to-end |
| 16 | اجرای واقعی گرید A3 روی دیتاست محلی | NOT_STARTED | نیازمند data/*.csv خارج از Git |

## بعدی
1) اجرای a3_grid.py + a3_breakout.py روی دیتاست محلی → N≥10، M=2.
2) تولید gates report با CLI و ثبت شاهد `docs/evidence/a3_grid_report.md`.
3) `access_log.jsonl` برای خواندن OOS.
