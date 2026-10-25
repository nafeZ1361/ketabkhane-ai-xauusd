EXEC_ENV_AVAILABLE

# A2.1 — اسکلت رابط کاربری (read-only)

- تاریخ: 2026-10-25
- دامنه: `/health` و `/quality`، فقط خواندنی، فقط localhost
- وابستگی جدید: **هیچ**

## ساخته‌شده
`docs/UI_CONTRACT.md`، `src/xauusd_research/ui/server.py`، `__main__.py`، `tests/test_ui.py`.

## نتیجهٔ آزمون‌ها
۵ آزمون HTTP سبز:
`test_health`, `test_quality`, `test_quality_without_audit_file`, `test_unknown_route`, `test_write_methods_rejected`.

## اجرای زنده
```
/health  -> status=ok api=1.0 version=0.1.0-mvp time=2026-10-25T15:55:20+00:00
/quality -> rows=3489359 sha=e539f7778885 gaps>60s=6505
/nope    -> HTTP 404
```

## معیارهای پذیرش
| معیار | وضعیت |
|---|---|
| سند قرارداد | ✅ |
| endpointها اجراشدنی | ✅ |
| تست‌های HTTP | ✅ ۵/۵ |
| بدون تغییر موتور | ✅ |
| بدون وابستگی جدید | ✅ |
