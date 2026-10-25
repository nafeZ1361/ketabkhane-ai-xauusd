# شاهد R1 — Rule-AST + موتور قطعی + مولد با seed

- تاریخ: 2026-10-26 | مرجع: `docs/research/SQX_BLUEPRINT.md` (بخش‌های B/C/D، فاز H جدول نقشه‌راه)، ADL-006/ADL-007
- مرز: صرفاً research/paper. هیچ کدزایی MT5 و هیچ ادعای سودآوری.

## آنچه ساخته شد

| فایل | نقش |
|---|---|
| `src/xauusd_research/rule_ast.py` | درخت قوانین سریال‌پذیر (Ind/Price/Const/Compare/Logic/ExitRule/RuleStrategy) + گاردها + JSON↔hash |
| `src/xauusd_research/rule_engine.py` | بک‌تست نوار‌به‌نوار AST با fill در بازِ i+1، SL/TP بدبینانه، مدل هزینه منجمد (ADL-004) |
| `src/xauusd_research/rule_generator.py` | مولد تصادفی با seed — ورودی یکسان ⇒ درخت بایت‌یکسان |
| `tests/test_rule_ast.py` | ۱۳ آزمون پذیرش AT-R1-* |

## فرمان و خروجی واقعی

```
$ python -m pytest tests/ -q
127 passed in 8.06s          # پیش‌تر ۱۱۴؛ +۱۳ آزمون جدید AT-R1

$ python artifacts/r1_smoke.py   # ۱۰۰ استراتژی seed=20261026 روی fixture ۵۰۰ کندل
strategies=100 candles=500 elapsed=0.28s sigs_with_trades=64 batch_hash=cca6d37bce8bc962
determinism: PASS (generation + engine)
```

بازتولید: اجرای دوم smoke دقیقاً همان `batch_hash=cca6d37bce8bc962` و همان متریک‌ها را داد (دو بار اجرا در ترمینال، خروجی یکسان).

## معیار خروج فاز R1 (طبق blueprint بخش H)

- «تولید پایدار هزاران استراتژی»: ✅ `test_seed_reproducibility_thousands` — ۲۰۰۰ استراتژی با seed=42، هش‌ها بایت‌به‌بایت یکسان و >۱۵۰۰ هش یکتا (تنوع واقعی).
- علیت/بدون leakage: ✅ `test_signals_are_causal` (برش آینده سیگنال گذشته را عوض نمی‌کند) + `test_next_bar_fill_no_lookahead`.
- قطعی بودن موتور: ✅ `test_deterministic_double_run` + assert دوتایی در smoke.

## محدودیت‌های صریح

- اعداد fixture مصنوعی‌اند؛ **هیچ نتیجه مالی** از این فاز استخراج نمی‌شود (۶۴/۱۰۰ استراتژی تریددار فقط یعنی موتور کار می‌کند).
- ژنتیک جزیره‌ای (فاز R2) و اتصال به ledger/gates (A2.5) هنوز انجام نشده؛ تولید انبوه روی داده واقعی در شاخه فعلی مجاز نیست تا تأیید انسانی.
