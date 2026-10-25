# سبک کار و الزامات مهندسی این مخزن

سند مرجع برای هر عامل (انسانی یا AI) که روی این مخزن کار می‌کند.
مطابق `AGENTS.md` بند ۶، تغییرات با شاهد ثبت می‌شوند؛ این سند «چگونه» را قفل می‌کند.

## ۱. هویت پروژه
پژوهش کمیِ قابل ممیزی XAUUSD: دادهٔ خام → استراتژی → اعتبارسنجی آماری.
هیچ ادعای سودآوری بدون OOS معتبر ممنوع. معاملهٔ واقعی/MT5 تا فاز C ممنوع.

## ۲. قوانین سخت (تخطی‌ناپذیر)
1. کامیت **نشدن** CSV/TSV دیتای بازار، اسرار، و هر فایل > ۵MB.
   (`tests/fixtures/synthetic_500.csv` تنها فایل دادهٔ کامیت‌شده است.)
2. `legacy/source/` آرشیو خواندنی: هرگز import/exec/edit نمی‌شود.
3. معیار پذیرش **پیش از** اجرا ثبت می‌شود (prereg + sha256)؛ تغییر آستانه پس از دیدن نتیجه ممنوع.
4. حداکثر سه تلاش برای هر مسئله، هر تلاش با فرضیهٔ ریشه‌ای متفاوت (`docs/OPEN_ISSUES.md`).
5. به‌جای حدس: «نامشخص». هر ادعا باید فایل/فرمان/تست به‌عنوان شاهد داشته باشد.
6. کد هسته و لایهٔ اعتبارسنجی **stdlib-only** است (بدون وابستگی شخص ثالث) تا همه‌جا قابل بازتولید و ممیزی باشد.

## ۳. ساختار پوشه‌ها (کار جدید کجا می‌نشیند)
| مسیر | نقش |
|---|---|
| `src/xauusd_research/` | هستهٔ MVP-1: schema, timezones, validation, strategies, costs, backtest, stream, report, cli, ui |
| `validation/` | لایهٔ A2.5: splits, metrics (PSR/DSR/PBO/bootstrap), ledger, gates + `gates.yaml` قفل‌شده با `gates.sha256` + `prereg/` |
| `scripts/` | ابزارهای یک‌بارمصرف/اجرای آزمایش (a3_grid.py, quality.py, audit_dataset.py, hash_gates.py, ...) |
| `tests/` | pytest؛ تست‌های acceptance با شناسهٔ `AT-*` در docstring |
| `docs/evidence/` | شواهد اجرای واقعی (markdown با فرمان + خروجی + تاریخ) |
| `docs/` | CURRENT_STATE (منبع یگانه وضعیت)، DECISION_LOG، OPEN_ISSUES، چارترها، A3_SCOPE |
| `AI_MEMORY/` | نقطهٔ شروع عامل: 00_START_HERE، 01_STATE (فشرده)، 02_LEDGER (دفتر کار با شاهد) |
| `vault/STATUS.md` | برچسب مرحله — همگام با CURRENT_STATE |
| `artifacts/`, `data/` | تولیدی و دیتای محلی — gitignored، هرگز کامیت نمی‌شود |

## ۴. قرارداد تعهد (commit)
- قالب: `<type>(<scope>): <summary>` — type ∈ feat|fix|docs|test|chore؛ scope = ماژول (validation, a2.5, ui, costs, oos, ...).
- summary انگلیسی، امری، ≤ ~۷۲ کاراکتر. بدنه (اختیاری): تصمیم/شاهد/عدد تست.
- هر commit باید test-suite سبز بگذارد.

## ۵. ژرف‌نویسی (docstring/comment)
- Docstring انگلیسی، فنی، مختصر؛ در ابتدایش ارجاع به سند حاکم
  (مثلاً `Charter v2.0 section 14`) و شناسهٔ acceptance test.
- مستندات فارسی (`docs/*.md`, `AI_MEMORY/*`) روان‌ترین حالت: جملات کوتاه، جدول، لینک به شاهد.
- تکرار وضعیت در چند فایل ممنوع؛ `docs/CURRENT_STATE.md` منبع یگانه است.

## ۶. جریان کار استاندارد (هر گام جدید)
1. خواندن `AI_MEMORY/00_START_HERE.md` → `01_STATE.md` → `02_LEDGER.md` (جلوگیری از کار تکراری).
2. ثبت پیش‌ثبت/تصمیم در `DECISION_LOG.md` (اگر معیار یا دامنه عوض می‌شود) + قفل هش (`scripts/hash_gates.py`).
3. پیاده‌سازی کوچک + تست هدفمند در همان commit.
4. اجرای `python -m pytest tests/` (سبز بودن الزامی) و در صورت نیاز `scripts/quality.py`.
5. نوشتن شاهد در `docs/evidence/<topic>.md` با فرمان دقیق و خروجی واقعی.
6. همگام‌سازی `CURRENT_STATE.md`، `AI_MEMORY/01_STATE.md`، `02_LEDGER.md`، `vault/STATUS.md`.
7. commit با قالب بند ۴؛ PR رو به `main` با تأیید انسانی (merge خودکار ممنوع).

## ۷. الزامات تست
- تست‌های عددی deterministic: seed صریح، بدون وابستگی به شبکه/زمان.
- Acceptance testها با شناسه: `AT-STAT-01..06` (اعتبارسنجی آماری)، `AT-*` سایر فازها.
- هیچ تستی بدون ثبت دلیل skip نمی‌شود (قاعدهٔ OPEN_ISSUES).
- پوشش خط ≥ ۸۰٪ گیت `scripts/quality.py`؛ فعلی ≈ ۹۵٪.

## ۸. ثبات‌بخشی محیط اجرا
- پلاگین معیوب `libtmux/pytest_plugin` در image پایتون باعث کرش collect می‌شود.
  فرمان استاندارد اجرای تست:
  `python -m pytest tests/ -p no:libtmux`
- Python ≥ 3.10، stdlib-only برای `src/` و `validation/`.

## ۹. الگوی طراحی لایهٔ اعتبارسنجی
- `ledger.py`: JSONL append-only با زنجیرهٔ هش (canonical JSON: sorted keys، separators فشرده).
- `metrics.py`: PSR/DSR/CSCV-PBO/moving-block bootstrap از اولprinciples با `random.Random(seed)`.
- `gates.py`: تفکیک الزامی FAIL از INSUFFICIENT_EVIDENCE؛ خروجی JSON ثابت
  `{verdict, gates, metrics, config_hash, data_version_hash, seed}`.
- `splits.py`: فقط حساب index (walk-forward با purge/embargo) — بدون I/O و بدون metric.
- مرز اخلاق: اسکریپت‌ها بدون دیتای واقعی «عدد جعلی» تولید نمی‌کنند
  (`refusing to fabricate evidence`).
