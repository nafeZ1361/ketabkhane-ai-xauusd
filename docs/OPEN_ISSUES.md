# مسائل باز

| شناسه | شدت | شرح | شواهد | تلاش | وضعیت | شرط بسته‌شدن |
|---|---|---|---|---|---|---|
| ISSUE-2026-0001 | high | مشخصات بروکر مستند شد اما اسپرد ثابت (میانه) فرض شده و اسلیپیج/سواپ مدل‌شدهٔ واقعی نیست | `docs/evidence/cost_run_full.md` | 1 | RESOLVED (با محدودیت) | اسپرد متغیر/تیک‌داده و اسلیپیج واقعی |
| ISSUE-2026-0002 | high | منشأ و مجوز انتشار دیتاست تأیید نشده | `docs/evidence/data_audit.md` | 1 | OPEN | تأیید منشأ/مجوز |
| ISSUE-2026-0003 | high | مهندسی معکوس Builder StrategyQuant در `LEGAL_HOLD` | `docs/PROJECT_CHARTER.md` | 0 | BLOCKED | تصمیم حقوقی ثبت‌شده |
| ISSUE-2026-0004 | low | نبود `pytest`/`coverage`؛ جایگزین `unittest` + tracer داخلی | `docs/evidence/coverage.md` | 1 | RESOLVED | — |
| ISSUE-2026-0005 | high | قالب TSV با هدر `<DATE>` پذیرفته نمی‌شد | `tests/test_tsv.py` | 1 | RESOLVED | تشخیص جداکننده + نرمال‌سازی هدر |
| ISSUE-2026-0006 | high | اعمال DST توسط سرور بروکر مستقل تأیید نشده | `docs/evidence/full_dataset_run.md` | 1 | OPEN | تأیید تنظیم Export و DST |
| ISSUE-2026-0007 | medium | `VOL` در ۹۳٪ ردیف‌ها صفر است؛ منبع حجم `TICKVOL` | `docs/evidence/data_audit.md` | 0 | OPEN | تصمیم ثبت‌شده دربارهٔ منبع حجم |
| ISSUE-2026-0008 | high | نبود پردازش جریانی برای کل دیتاست | `docs/evidence/full_dataset_run.md` | 1 | RESOLVED | موتور جریانی + هم‌ارزی اثبات‌شده |
| ISSUE-2026-0009 | high | MA 5/20 اقتصادی نبود (ناخالص منفی، ۱۱۴ هزار معامله) | `docs/evidence/strategy_attempts.md` | 3 | RESOLVED (تلاش ۳) | MA 100/400 + فیلتر روند |
| ISSUE-2026-0010 | high | اعتبارسنجی خارج از نمونه: دادهٔ M1 معتبر در دسترس نیست | `docs/evidence/out_of_sample_validation_2008_2015.md` | 0 | DEFERRED | دادهٔ M1 ۲۰۰۸–۲۰۱۵ یا دادهٔ پس از ۲۰۲۶-۱۰-۰۹ |
| ISSUE-2026-0011 | high | مدل‌سازی هزینهٔ واقعی (اسلیپیج + سواپ) | `docs/evidence/cost_modeling.md` | 1 | RESOLVED | سناریوی کامل مثبت ماند |
| ISSUE-2026-0012 | medium | نبود گیت CI روی GitHub؛ تست‌ها فقط محلی اجرا می‌شدند و امکان false-green داشتند | PR #1 (`a22ae23`)، PR #2 (`229a65d`)، artifact `ci_evidence.json` (run 40694483115: passed=109, failed=0) | 3 | RESOLVED | `.github/workflows/ci.yml` (gate تست + evidence JSON) و `.github/workflows/gov-drift.yml` (نگهبان drift روزانه) فعال و سبز روی main |

| DATA_2008_2015_RECOVERY | high | تأمین دادهٔ M1 معتبر ۲۰۰۸–۲۰۱۵ (بروکر فعلی → Dukascopy → HistData)؛ سقف سه تلاش | `docs/evidence/out_of_sample_validation_2008_2015.md` | 1 | OPEN | داده با ≥ ۳۰ معامله در OOS یا پذیرش رسمی BLOCKED |

| ISSUE-2026-0016 | medium | دو بلاب ~۱۸ مگابایتی (CSV و RAR) در تاریخچهٔ گیت باقی مانده‌اند؛ پاک‌سازی نیازمند force-push با مجوز صریح | `git log --all -- XAUUSD*` | 0 | OPEN | مجوز صریح + بازنویسی تاریخچه (filter-repo) |

## قواعد
- هر مسئله حداکثر سه تلاش دارد؛ هر تلاش باید فرضیهٔ ریشه‌ای متفاوت داشته باشد.
- هیچ تستی بدون دلیل و بدون ثبت در همین سند skip نمی‌شود.
