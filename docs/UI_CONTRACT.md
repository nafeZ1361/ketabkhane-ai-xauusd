# قرارداد رابط کاربری (UI Contract) — فاز A2.1

- نسخهٔ API: `1.0`
- وضعیت: فقط خواندنی (read-only)
- دامنه: `127.0.0.1` فقط

## قواعد عمومی

| مورد | قاعده |
|---|---|
| قالب | JSON با کدگذاری UTF-8 (`Content-Type: application/json; charset=utf-8`) |
| متد مجاز | فقط `GET` (سایر متدها → `405`) |
| زمان | ISO-8601 با منطقهٔ زمانی UTC و پسوند `+00:00` |
| پول | دلار آمریکا (USD)، عدد اعشاری |
| قیمت | واحد ارز مظنه (برای XAUUSD: دلار بر اونس) |
| point | عدد صحیح |
| نسخه | هر پاسخ موفق شامل `api_version` است |

## 1) `GET /health`

پاسخ `200`:

```json
{
  "api_version": "1.0",
  "status": "ok",
  "service": "xauusd-research-ui",
  "package_version": "0.1.0-mvp",
  "time_utc": "2026-10-25T19:40:00+00:00",
  "checks": {
    "data_audit_present": true,
    "root": "C:\\...\\ketabkhane-ai-xauusd"
  }
}
```

| فیلد | نوع | معنا |
|---|---|---|
| `status` | string | همیشه `ok` در پاسخ موفق |
| `package_version` | string | نسخهٔ پکیج پروژه |
| `time_utc` | string | زمان سرور در لحظهٔ پاسخ |
| `checks.data_audit_present` | bool | وجود فایل ممیزی داده |

## 2) `GET /quality`

پاسخ `200`:

```json
{
  "api_version": "1.0",
  "source": {"path": "docs/evidence/data_audit.json", "sha256": "..."},
  "dataset": {
    "path": "...XAUUSD_M1_...csv",
    "sha256": "...",
    "bytes": 214692947,
    "rows": 3489359,
    "columns": ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL", "VOL", "SPREAD"],
    "time_reference": "SERVER_TIME_NAIVE",
    "first_time": "2016-10-03T01:00:00",
    "last_time": "2026-10-09T23:54:00",
    "per_year": {"2016": 87329}
  },
  "integrity": {
    "column_mismatch": 0, "numeric_errors": 0, "ohlc_errors": 0,
    "non_positive_price": 0, "duplicate_time": 0, "out_of_order": 0, "negative_spread": 0
  },
  "zeros": {"tickvol": 3, "volume": 3251252, "spread": 57},
  "gaps": {
    "bar_interval_seconds": 60,
    "greater_than_60s": 6505,
    "greater_than_12h": 538,
    "largest": [{"seconds": 451560, "from": "2017-09-26 19:35:00", "to": "2017-10-02 01:01:00"}]
  },
  "price_range": {"min_low": 1122.62, "max_high": 5596.58}
}
```

| فیلد | نوع | معنا |
|---|---|---|
| `source.sha256` | string | هش فایل ممیزی که این پاسخ از آن ساخته شده |
| `dataset.time_reference` | string | `SERVER_TIME_NAIVE` یعنی زمان‌ها به وقت سرور بروکر و بدون منطقهٔ زمانی‌اند (تبدیل به UTC در موتور انجام می‌شود) |
| `dataset.first_time` / `last_time` | string | ISO-8601 بدون offset (چون مبدأ سرور است) |
| `integrity.*` | int | شمارش خطاها؛ صفر = سالم |
| `zeros.*` | int | تعداد مقادیر صفر در ستون‌ها |
| `gaps.bar_interval_seconds` | int | فاصلهٔ غالب کندل‌ها |
| `gaps.largest` | array | ۱۰ شکاف بزرگ |

## 3) خطاها

قالب یکسان برای همهٔ خطاها:

```json
{
  "api_version": "1.0",
  "error": {"status": 404, "code": "NOT_FOUND", "message": "no route for GET /nope"}
}
```

| کد | HTTP | معنا |
|---|---|---|
| `NOT_FOUND` | 404 | مسیر وجود ندارد |
| `METHOD_NOT_ALLOWED` | 405 | متد غیر از GET |
| `AUDIT_MISSING` | 503 | فایل `docs/evidence/data_audit.json` موجود نیست |

## 4) امنیت

- سرور فقط روی `127.0.0.1` گوش می‌دهد؛ روی شبکهٔ محلی منتشر نمی‌شود.
- هیچ نوشتن، آپلود یا اجرای فرمانی وجود ندارد.
- پاسخ‌ها `Cache-Control: no-store` دارند.

## 5) خارج از دامنهٔ A2.1

- فرم اجرای آزمایش، صفحهٔ نتایج و هر عملیات نوشتنی → فاز A2.2 و A2.3.