# راهنمای ادامهٔ کار — برای هر هوش مصنوعی

این فایل نقطهٔ شروع است. هر عامل جدید باید پیش از هر کاری این را بخواند و سپس به اسناد ارجاع‌شده برود.

## 0. هویت پروژه

- مخزن: `nafeZ1361/ketabkhane-ai-xauusd` (عمومی)
- شاخهٔ کاری: `main` | شاخهٔ کمکی: `stage-0/legacy-import` (آینهٔ main)
- پوشهٔ محلی: `C:\Users\icFixer.ir\Desktop\ketabkhane-ai-xauusd`
- زبان مستندات: فارسی | شناسه‌ها، فایل‌ها و APIها: انگلیسی
- محیط اجرا: `EXEC_ENV_AVAILABLE` (ویندوز، Python 3.12/3.11، بدون وابستگی خارجی)

## 1. ترتیب خواندن

1. `docs/PROJECT_CHARTER.pdf` — سند مادر (نسخهٔ ۱، مرجع اصلی)
2. `docs/PROJECT_CHARTER.md` — متن استخراج‌شدهٔ همان سند
3. `docs/PROJECT_CHARTER_V2.pdf` + `.md` — پرامپت مادر نسخهٔ ۲ (فازبندی و قواعد اجرایی)
4. `docs/CURRENT_STATE.md` — وضعیت واقعی و گام مجاز بعدی
5. `docs/OPEN_ISSUES.md` — مسائل باز با شناسه و شرط بسته‌شدن
6. `docs/DECISION_LOG.md` — ۲۲ تصمیم ثبت‌شده (شامل معیارهای پیش‌ثبت‌شده)
7. `docs/ROADMAP.md` — نقشهٔ راه فاز A (UI، DSL، بهینه‌ساز)
8. `docs/UI_CONTRACT.md` — قرارداد API رابط کاربری
9. `docs/WORKING_STYLE.md` — سبک کار و قراردادهای مخزن (الزامی برای هر عامل)
10. `docs/research/SQX_BLUEPRINT.md` — طرح‌نامه مفهومی StrategyQuant X (مرجع طراحی فاز Research Factory؛ طبق ADL-006 صرفاً مرجع است، نه الزام)

## 2. وضعیت فعلی (۲۰۲۶-۱۰-۲۵)

- موتور: بک‌تست حافظه‌ای و جریانی (هم‌ارزی اثبات‌شده)، بارگذار CSV/TSV با تبدیل زمان سرور به UTC، اعتبارسنجی داده، مدل هزینه (اسپرد/اسلیپیج/سواپ)، خروجی معاملات و manifest با SHA-256.
- استراتژی: `ma_100_400` + فیلتر روند ۵۰۰ → **نامزد تأیید**؛ تأیید نهایی منوط به دادهٔ M1 خارج از نمونه (`ISSUE-2026-0010` = DEFERRED).
- رابط کاربری: A2.1 (`/health`, `/quality`) و A2.2 (`/`, `/datasets`, `POST /runs`, `GET /runs/{id}`) انجام شده.
- آزمون‌ها: ۸۶ آزمون، پوشش ~۹۵٪، `scripts/quality.py` سبز.

## 3. دستورهای اجرا

```powershell
# آزمون‌ها و پوشش
python scripts\quality.py

# بررسی سالم‌بودن کدگذاری اسناد (باید صفر باشد)
python scripts\check_encoding.py

# اجرای یک آزمایش روی داده (نمونه)
python run_mvp.py run --csv data\sample_300k.tsv --out artifacts\demo --mode stream --strategy ma_100_400 --trend-window 500 --broker-profile config\scenario_s3.json

# رابط کاربری محلی (خواندن + اجرا)
python -m xauusd_research.ui --port 8765
# http://127.0.0.1:8765/
```

## 4. نقشهٔ فایل‌ها

| مسیر | نقش |
|---|---|
| `src/xauusd_research/` | هستهٔ موتور: `schema`, `validation`, `timezones`, `strategies`, `backtest`, `stream`, `costs`, `report`, `cli` |
| `src/xauusd_research/ui/` | سرور محلی و API |
| `tests/` | ۸۶ آزمون + fixture مصنوعی |
| `scripts/` | `quality`, `check_encoding`, `audit_dataset`, `check_parity`, `make_fixture`, `sweep`, `run_full` |
| `config/` | پروفایل هزینهٔ بروکر و سناریوها (`scenario_s1/s2/s3`) |
| `docs/` | منشور، وضعیت، تصمیم‌ها، مسائل، نقشهٔ راه، قرارداد UI |
| `docs/evidence/` | شواهد آزمون‌ها، ممیزی داده، اجراها، حساسیت اسپرد |
| `legacy/source/` | آرشیو کتابخانهٔ قدیمی — فقط خواندنی، هرگز import نشود |
| `data/` | دادهٔ محلی (gitignored) — هرگز کامیت نشود |

## 5. قواعد غیرقابل مذاکره (خلاصهٔ منشور)

- هیچ ادعایی بدون شواهد قابل بررسی پذیرفته نمی‌شود؛ وضعیت‌ها: VERIFIED / FAILED / BLOCKED / UNKNOWN / PROPOSED / NOT_RUN / WAIVED.
- معیارهای پذیرش را **پیش از اجرا** در `DECISION_LOG.md` ثبت کن؛ تغییر پس از دیدن نتیجه ممنوع.
- نتیجهٔ منفی معتبر، بهتر از نتیجهٔ مثبت نامعتبر است.
- هر مسئله حداکثر سه تلاش با فرضیهٔ ریشه‌ای متفاوت.
- هیچ معاملهٔ واقعی، اتصال MT5 یا ارسال سفارش بدون دروازهٔ مستقل و مجوز صریح کاربر.
- دادهٔ CSV/TSV، اسرار، کلید و فایل بزرگ‌تر از ۵ مگابایت کامیت نمی‌شود.
- `legacy/source/` هرگز اجرا یا import نمی‌شود.
- مهندسی معکوس Builder StrategyQuant در `LEGAL_HOLD` است.

## 6. نکات فنی که باید بدانی

- **زمان:** فایل‌های متاتریدر به وقت سرور بروکر (Europe/Kyiv) هستند؛ بارگذار با `eu-dst` به UTC تبدیل می‌کند. ساعت ناموجود بهار و تکراری پاییز رد می‌شوند.
- **قالب ورودی:** TSV با هدرهای `<DATE>`؛ تشخیص جداکننده خودکار است.
- **هزینه:** اسپرد ۳۰ point (میانهٔ دیتاست)، کمیسیون ۰ (از تاریخچهٔ معاملات)، اسلیپیج ۲ point رفت‌وبرگشت، سواپ ۰٫۰۱٪/شب (فرضی).
- **برچسب‌ها:** `NO_TRADING_COSTS` / `PROVISIONAL_COST_SCENARIO` / `VERIFIED_COSTS` و `pnl_unit` در `summary.json`.
- **هم‌ارزی موتورها:** هر تغییر در محاسبات باید با `scripts/check_parity.py` تأیید شود (ترتیب جمع ممیز شناور مهم است).
- **کدگذاری اسناد:** فایل‌های فارسی فقط با UTF-8 صریح (Python یا ویرایشگر) نوشته شوند؛ هرگز با `Get-Content` در PowerShell 5.1 بازنویسی نشوند (باعث mojibake می‌شود). `scripts/check_encoding.py` باید صفر بدهد.

## 7. مسائل باز و گام بعد

- `ISSUE-2026-0010` (DEFERRED): بدون دادهٔ M1 دیده‌نشده، هیچ تأیید نهایی مجاز نیست.
- `ISSUE-2026-0002/0006/0007`: مجوز داده، تأیید DST، منبع حجم.
- گام بعدی طبق `docs/ROADMAP.md`: **A2.3** — صفحهٔ نتایج (`/runs/{id}` نمایش معیارها و جدول معاملات) و سپس A3 (DSL و بهینه‌ساز).

## 8. قرارداد به‌روزرسانی وضعیت

پس از هر کار:
1. `docs/CURRENT_STATE.md` را به‌روز کن (فاز، وضعیت گیت، گام بعد).
2. تصمیم جدید را در `docs/DECISION_LOG.md` با شناسهٔ بعدی ثبت کن.
3. مسئلهٔ جدید یا تغییر وضعیت را در `docs/OPEN_ISSUES.md` ثبت کن.
4. شواهد را در `docs/evidence/` بگذار و در گزارش به آن لینک بده.
5. `python scripts/quality.py` و `python scripts/check_encoding.py` را اجرا کن؛ هر دو باید سبز باشند.
6. کامیت با پیام انگلیسی و push به `main`.
