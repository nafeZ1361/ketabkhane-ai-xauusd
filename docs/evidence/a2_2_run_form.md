EXEC_ENV_AVAILABLE

# A2.2 — فرم اجرای آزمایش (Run Form)

- تاریخ: 2026-10-25
- دامنه: `GET /`، `GET /datasets`، `POST /runs`، `GET /runs/{id}`
- وابستگی جدید: **هیچ** (stdlib: `http.server`, `json`, `uuid`, `threading`)
- موتور بک‌تست و استراتژی: **بدون تغییر**

## آنچه ساخته شد

| فایل | نقش |
|---|---|
| `src/xauusd_research/ui/server.py` | صف در حافظه، اعتبارسنجی ورودی، اجرای Thread، صفحهٔ HTML |
| `tests/test_ui_runs.py` | ۱۰ آزمون HTTP (چرخهٔ اجرا، امنیت، خطاها) |
| `docs/UI_CONTRACT.md` | بخش‌های ۶ تا ۱۱ اضافه شد |

## اجرای زنده (سرور واقعی روی 127.0.0.1:8765)

```
/                 -> HTTP 200  html_bytes=2827  has_select=True
POST /runs        -> status=QUEUED  run_id=49b038e5ff14
GET /runs/<id>    -> status=COMPLETED  trades=9890  cost=PROVISIONAL_COST_SCENARIO
traversal         -> HTTP 400
```

اجرای واقعی روی `data/sample_300k.tsv` با پروفایل `config/scenario_s1.json` انجام شد و خروجی در `artifacts/ui_runs/<id>/` نوشته شد.

## آزمون‌ها

```
Ran 86 tests ... OK      (کل پروژه)
quality gate: PASS       coverage 95.58%
```

آزمون‌های جدید A2.2:

| آزمون | چه چیزی را ثابت می‌کند |
|---|---|
| `test_page_renders_form` | صفحهٔ HTML با selectها سرو می‌شود |
| `test_datasets_listing` | فقط فایل‌های `data/` فهرست می‌شوند |
| `test_run_lifecycle` | POST → QUEUED، سپس COMPLETED با metrics |
| `test_path_traversal_is_rejected` | `../secret.csv` → 400 |
| `test_absolute_path_is_rejected` | `C:\Windows\win.ini` → 400 |
| `test_unknown_strategy` / `test_unknown_profile` / `test_missing_dataset` | اعتبارسنجی ورودی |
| `test_unknown_run` | 404 برای شناسهٔ ناموجود |
| `test_invalid_json_body` | بدنهٔ نامعتبر → 400 |

## معیارهای پذیرش

| معیار | وضعیت |
|---|---|
| قرارداد UI به‌روز شد | ✅ |
| `POST /runs` و `GET /runs/{id}` کار می‌کنند | ✅ (اجرای زنده + تست) |
| صفحهٔ HTML اجرا می‌شود و آزمایش را شروع می‌کند | ✅ |
| بدون وابستگی جدید | ✅ |
| موتور/استراتژی بدون تغییر | ✅ |
| همهٔ تست‌های HTTP سبز | ✅ ۸۶/۸۶ |

## محدودیت‌ها

- صف در حافظه است؛ با ری‌استارت سرور، تاریخچهٔ اجراها از دست می‌رود (خروجی‌ها در `artifacts/` می‌مانند).
- یک اجرا در هر لحظه محدودیت ندارد؛ چند اجرا هم‌زمان ممکن است (Thread جداگانه).
- احراز هویت وجود ندارد چون فقط localhost است.

## گام بعدی (A2.3)

صفحهٔ نتایج: نمایش معیارها، جدول معاملات صفحه‌بندی‌شده، نمایش موانع/خطاها و لینک `manifest.json` برای همان `run_id`.
