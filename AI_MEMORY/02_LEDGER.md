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
| 11 | A2.5 اعتبارسنجی آماری | NOT_STARTED | — |
| 12 | ADL.md | DONE | docs/ADL.md |
| 13 | سند مادر ۲.۰ + AI_MEMORY | DONE | PROJECT_CHARTER_V3.md, AI_MEMORY |

## بعدی
1) `ADL.md` بساز (سند پنجم الزامی).
2) A2.5 را با ۵ آزمون و قرارداد JSON بساز.
3) `access_log.jsonl` برای خواندن OOS.
