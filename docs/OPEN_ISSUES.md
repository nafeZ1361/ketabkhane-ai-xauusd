# مسائل باز

| شناسه | شدت | شرح | شواهد | تالش | وضعیت | شرط بسته‌شدن |
|---|---|---|---|---|---|---|
| ISSUE-2026-0001 | high | مشخصات واقعی بروکر موجود نیست؛ نتایج فقط با `NO_TRADING_COSTS` معتبرند | `docs/DECISION_LOG.md` (DEC-2026-005) | 0 | OPEN | ارائهٔ مشخصات نماد/حساب و مدل هزینه |
| ISSUE-2026-0002 | high | منشأ و مجوز انتشار دیتاست تأیید نشده | `docs/evidence/data_audit.md` | 1 | OPEN | تأیید منشأ/مجوز |
| ISSUE-2026-0003 | high | مهندسی معکوس Builder StrategyQuant در `LEGAL_HOLD` | `docs/PROJECT_CHARTER.md` بند ۴.۳ | 0 | BLOCKED | تصمیم حقوقی ثبت‌شده |
| ISSUE-2026-0004 | low | نبود `pytest`/`coverage`؛ جایگزین `unittest` + tracer داخلی | `docs/evidence/coverage.md` | 1 | RESOLVED | — |
| ISSUE-2026-0005 | high | قالب TSV با هدر `<DATE>` پذیرفته نمی‌شد | `tests/test_tsv.py` | 1 | RESOLVED | تشخیص جداکننده + نرمال‌سازی هدر |
| ISSUE-2026-0006 | high | اعمال DST توسط سرور بروکر مستقل تأیید نشده (سیاست قابل تغییر است) | `docs/evidence/full_dataset_run.md` | 1 | OPEN | تأیید تنظیم Export و قاعدهٔ DST |
| ISSUE-2026-0007 | medium | `VOL` در ۹۳٪ ردیف‌ها صفر است؛ منبع حجم `TICKVOL` | `docs/evidence/data_audit.md` | 0 | OPEN | تصمیم ثبت‌شده دربارهٔ منبع حجم |
| ISSUE-2026-0008 | high | نبود پردازش جریانی برای کل دیتاست | `docs/evidence/full_dataset_run.md` | 1 | RESOLVED | موتور جریانی + هم‌ارزی اثبات‌شده (۵۳۴ ثانیه، اوج ۵۹ مگابایت) |

## قواعد
- هر مسئله حداکثر سه تالش دارد؛ هر تالش باید فرضیهٔ ریشه‌ای متفاوت داشته باشد.
- هیچ تستی بدون دلیل و بدون ثبت در همین سند skip نمی‌شود.