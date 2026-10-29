# تحویل نهایی — وضعیت و راهنمای اجرا

- تاریخ: ۲۰۲۶-۱۰-۲۹
- نسخهٔ کاری: `a8aa44c` + اصلاحات این تحویل
- وضعیت کلی: **قابل اجرا و قابل واگذاری**؛ اعتبارسنجی آماری نهایی همچنان DEFERRED

## ۱. چه چیزی تحویل داده می‌شود

| بخش | وضعیت | مسیر |
|---|---|---|
| موتور داده و بک‌تست (حافظه‌ای + جریانی، هم‌ارزی اثبات‌شده) | آماده | `src/xauusd_research/` |
| بارگذار CSV/TSV + تبدیل زمان سرور به UTC | آماده | `schema.py`, `timezones.py` |
| مدل هزینه (اسپرد/اسلیپیج/سواپ) با پروفایل JSON | آماده | `costs.py`, `config/` |
| اجرای سریع تک‌فرمانی | آماده | `quick_run.py` |
| رابط کاربری محلی (health/quality/run/results API) | آماده (A2.2 منجمد) | `src/xauusd_research/ui/` |
| لایهٔ اعتبارسنجی آماری | لایهٔ اول: gates + splits | `validation/` |
| دفتر آزمایش و metrics (PSR/DSR/PBO) | **ساخته نشده** | — |
| CI + drift sentinel | آماده | `.github/workflows/` |
| تست‌ها | سبز (unittest؛ pytest در CI) | `tests/` |

## ۲. اجرا در ۳ دستور

```powershell
python run_mvp.py run --csv tests\fixtures\synthetic_500.csv --out artifacts\demo --mode memory
python -m xauusd_research.ui --port 8765
python scripts\quality.py
```

## ۳. کنترل‌های کیفیت اجباری قبل از هر تحویل

```powershell
python scripts\check_encoding.py
python scripts\check_repo_hygiene.py
python scripts\quality.py
python -m unittest discover -s tests -t .
```

## ۴. موانع باز (صادقانه)

| شناسه | وضعیت | معنا |
|---|---|---|
| ISSUE-2026-0010 | DEFERRED | دادهٔ M1 دیده‌نشده برای OOS وجود ندارد |
| DATA_2008_2015_RECOVERY | OPEN | تلاش برای تأمین داده (سقف سه تلاش) |
| DSR/PBO | INACTIVE | با N<10 و M<2 عدد گزارش نمی‌شود |
| ISSUE-2026-0002/0006/0007 | OPEN | مجوز داده، تأیید DST، منبع حجم |
| ISSUE-2026-0003 | BLOCKED | مهندسی معکوس SQ در LEGAL_HOLD |

هیچ ادعای سودآوری مجاز نیست؛ استراتژی نامزد `DEFERRED_NO_VALID_OOS` است.

## ۵. ریسک باقی‌ماندهٔ مخزن

دو فایل بزرگ (CSV و RAR حدود ۱۸ مگابایت) از طریق آپلود وب وارد تاریخچه شده‌اند. این تحویل آن‌ها را از ردیابی خارج کرد و قاعدهٔ `check_repo_hygiene.py` را اضافه کرد، اما **حجم آن‌ها در تاریخچهٔ گیت باقی است**؛ پاک‌سازی کامل نیازمند بازنویسی تاریخچه و force-push با مجوز صریح است.

## ۶. گام بعد برای عامل بعدی

1. `python scripts\check_repo_hygiene.py` و `quality.py` را اجرا کن؛ هر دو باید سبز باشند.
2. `validation/ledger.py` و `metrics.py` (PSR/DSR/PBO/بوت‌استرپ) را بساز.
3. گرید A3 (بدون GA) برای رسیدن به N≥10 و M≥2.
4. پس از فعال‌شدن آستانه‌ها، `gates.yaml` را به‌روز و `config_hash` را دوباره ثبت کن.

## History Debt (Layer 2)
دو بلاب ~۱۸MB در تاریخچهٔ گیت باقی است (`git log --all -- XAUUSD*`). گزینه‌ها: `git filter-repo` یا BFG + force-push. **بدون مجوز صریح اجرا نمی‌شود.**
