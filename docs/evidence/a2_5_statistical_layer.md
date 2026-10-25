# شاهد — تکمیل لایهٔ اعتبارسنجی آماری A2.5

- تاریخ: ۲۰۲۶-۱۰-۲۶ | ارجاع: DEC-2026-028، Charter v2.0 بخش ۱۴، `docs/A3_SCOPE.md`

## چه ساخته شد
| فایل | نقش |
|---|---|
| `validation/ledger.py` | دفتر آزمایش append-only با زنجیرهٔ هش SHA-256 (canonical JSON) |
| `validation/metrics.py` | PSR، DSR (E[max SR] حد بیش‌آزمون)، CSCV-PBO، moving-block bootstrap — stdlib-only، deterministic با seed صریح |
| `validation/gates.py` | ارزیابی گیت‌ها از `gates.yaml` قفل‌شده + تفکیک FAIL/INSUFFICIENT_EVIDENCE + CLI گزارش JSON |
| `scripts/a3_grid.py` | گرید پیش‌ثبت خانواده MA → ledger |
| `scripts/a3_breakout.py` | گرید پیش‌ثبت خانواده Donchian (entry∈{20,55}, exit=10) → ledger؛ شرط M≥2 برای PBO |
| `docs/WORKING_STYLE.md` | سند سبک کار و الزامات مهندسی مخزن |

## فرمان‌های بازتولید
```bash
python -m pytest tests/test_statistical_validation.py -p no:libtmux   # 22 passed
python -m pytest tests/ -p no:libtmux                                  # 114 passed
python scripts/check_encoding.py                                       # mojibake: 0
python -m validation.gates --ledger <experiments.jsonl> --out report.json
```

## نتایج کلیدی (آزمون‌های acceptance)
- AT-STAT-01 نویز خالص ⇒ PBO گیت را پاس نمی‌کند. ✅
- AT-STAT-02 لبه کاشته‌شده ⇒ شناسایی می‌شود. ✅
- AT-STAT-04 تکرارپذیری با seed ثابت. ✅
- AT-STAT-05 حذف/ویرایش رکورد دفتر ⇒ `intact=False` با پیام دقیق. ✅
- قرارداد خروجی: `{verdict, gates, metrics, config_hash, data_version_hash, seed}`. ✅
- صداقت محیط: بدون دیتاست، هر دو runner با exit code 2 و پیام
  «refusing to fabricate evidence» متوقف می‌شوند. ✅

## وضعیت گیت‌ها (بدون تغییر — دست‌نخورده)
- DSR: `INACTIVE_N_TOO_SMALL` (آستانه N=10)
- PBO: `INACTIVE_M_LESS_THAN_2` (runner دوم ساخته شد؛ فعال‌سازی نیازمند اجرای واقعی)
- OOS: `DEFERRED_NO_VALID_OOS`
- `config_hash` تأییدشده با `validation/gates.sha256`.

## محدودیت‌ها / گام بعد
- اجرای واقعی گریدها به دیتاست محلی (`data/XAUUSD_M1_*.csv`، خارج از Git) نیاز دارد.
- پس از اجرا: `docs/evidence/a3_grid_report.md` با جدول کامل نتایج (معیار خروج A3).
