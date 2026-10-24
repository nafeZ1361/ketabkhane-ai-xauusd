# مسائل باز

| شناسه | شدت | شرح | شواهد | تالش | وضعیت | شرط بسته‌شدن |
|---|---|---|---|---|---|---|
| ISSUE-2026-0001 | high | مشخصات واقعی بروکر (اسپرد، کمیسیون، سواپ، Contract size، Tick size/value، حداقل/گام حجم) موجود نیست؛ نتایج فقط با برچسب `NO_TRADING_COSTS` معتبرند | `docs/DECISION_LOG.md` (DEC-2026-005) | 0 | OPEN | ارائهٔ مشخصات مستند نماد/حساب و پیاده‌سازی مدل هزینه |
| ISSUE-2026-0002 | high | دیتاست: ساختار سالم است، اما منشأ و مجوز انتشار هنوز تأیید نشده | `docs/evidence/data_audit.md` | 1 | OPEN | تأیید منشأ/مجوز |
| ISSUE-2026-0003 | high | مهندسی معکوس Builder StrategyQuant در `LEGAL_HOLD` | `docs/PROJECT_CHARTER.md` بند ۴.۳ | 0 | BLOCKED | تصمیم حقوقی ثبت‌شده |
| ISSUE-2026-0004 | low | نبود `pytest`/`coverage`؛ جایگزین: `unittest` + tracer داخلی | `docs/evidence/coverage.md` | 1 | RESOLVED | — |
| ISSUE-2026-0005 | high | قالب TSV با هدر `<DATE>` توسط بارگذار پذیرفته نمی‌شد | `tests/test_tsv.py` | 1 | RESOLVED | تشخیص جداکننده + نرمال‌سازی هدر + آزمون |
| ISSUE-2026-0006 | high | منطقهٔ زمانی: بارگذار اکنون با سیاست `eu-dst`/`fixed+2`/`fixed+3`/`utc` کار می‌کند، اما اعمال DST توسط سرور بروکر به‌صورت مستقل تأیید نشده است | `docs/evidence/real_data_run.md`، `tests/test_timezones.py` | 1 | OPEN | تأیید تنظیم Export و قاعدهٔ DST بروکر |
| ISSUE-2026-0007 | medium | ستون `VOL` در ۹۳٪ ردیف‌ها صفر است؛ منبع حجم باید `TICKVOL` باشد | `docs/evidence/data_audit.md` | 0 | OPEN | تصمیم ثبت‌شده دربارهٔ منبع حجم |
| ISSUE-2026-0008 | high | بارگذار کل فایل (۳٬۴۸۹٬۳۵۹ ردیف) را در حافظه نگه می‌دارد؛ برای کل دیتاست باید پردازش جریانی/دسته‌ای اضافه شود | `docs/evidence/real_data_run.md` | 0 | OPEN | پیاده‌سازی حالت جریانی + آزمون حافظه |

## قواعد
- هر مسئله حداکثر سه تالش دارد؛ هر تالش باید فرضیهٔ ریشه‌ای متفاوت داشته باشد.
- هیچ تستی بدون دلیل و بدون ثبت در همین سند skip نمی‌شود.