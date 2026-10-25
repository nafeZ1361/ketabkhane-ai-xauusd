# طرح‌نامه مفهومی StrategyQuant X (SQX) و تطبیق با ketabkhane-ai-xauusd

> **منبع:** سند تحلیلی کاربر («تحلیل StrategyQuant X و پروپوزال بازسازی مفهومی» — نسخه تکمیلی و دقیق‌تر).
> **تاریخ ثبت:** 2026-10-26 | **ثبت‌کننده:** AI agent (کاربر: nafeZ1361)
> **وضعیت:** مرجع طراحی (design reference) — الزام پیاده‌سازی نیست. هر تغییر رفتار باید طبق ADL با تأیید انسانی باشد.

## برچسب‌های سطح اطمینان (مطرح در سند اصلی)

- **[ت]** تأییدشده با منبع رسمی/مستندات SQX
- **[د]** دانش عمومی — نیازمند تطبیق با نسخه Trial
- **[ط]** تصمیم طراحی برای بازسازی مفهومی

**محدودیت مهم:** مستندات رسمی Builder مربوط به ۲۰۱۹ است؛ نام/جای کنترل‌ها در بیلد ۱۴۳+ ممکن است متفاوت باشد. هرجا «نیازمند تطبیق» آمده، یعنی همین.

---

## A. تعریف محصول و فلسفه

- **A-1:** SQX نرم‌افزار دسکتاپ جاوا-محور است که استراتژی را خودکار تولید، آزمایش، اعتبارسنجی و صادر می‌کند (Win/Mac/Linux) [ت].
- **A-2 چرخه ارزش:**
  `داده → بلوک‌ها → مولد (تصادفی/ژنتیک) → بک‌تست → رتبه‌بندی/فیلتر → قیف Cross-check → Databank → پورتفوی → صدور کد → اجرا`
- **A-3 فنل (Funnel) مفهوم کلیدی است [ت]:** تست ارزان اول، تست گران آخر؛ ردشدگان خودکار حذف می‌شوند.
- **A-4 هزینه زمانی [ت]:** ~۰٫۲ ثانیه/استراتژی بدون Cross-check ولی ۱۰–۲۰۰ ثانیه با Cross-check ⇒ معماری باید تست گران را فقط روی بازماندگان اجرا کند.
- **A-5 سه سازوکار رسیدن به edge:** جست‌وجوی خودکار + فیلتر عملکرد + تست‌های ضد بیش‌برازش (Cross-check/OOS/WF).

## B. معماری لایه‌ای

| # | لایه | ورودی | خروجی | نکته حیاتی |
|---|---|---|---|---|
| ۱ | داده | CSV/تیک | سری OHLC یکسان‌شده | TZ، DST، شکاف، اسپرد |
| ۲ | بلوک‌ها | اندیکاتور/قاعده | کتابخانه قابل ترکیب | نام، پارامتر با بازه، نوع خروجی |
| ۳ | مولد | بلوک‌ها+قیود | استراتژی (درخت قوانین) | تصادفی یا ژنتیک |
| ۴ | موتور بک‌تست | استراتژی+داده+هزینه | معاملات+منحنی سرمایه | قطعی (deterministic) و سریع |
| ۵ | معیارها | لیست معاملات | شاخص‌ها | مشترک بین Fitness و فیلتر |
| ۶ | رتبه‌بندی | معیارها | پذیرش/رد | شرط ورود به Databank |
| ۷ | Cross-check | منتخب‌ها | گذر/رد+گزارش | Basic/Standard/Extensive [ت] |
| ۸ | Databank | منتخب‌ها | جدول قابل فیلتر | پیکربندی کامل برای بازتولید |
| ۹ | پورتفوی | چند استراتژی | وزن/همبستگی | Fit to Portfolio [ت] |
| ۱۰ | تولید کد | استراتژی | MQL/… | تطبیق عددی با پلتفرم |
| ۱۱ | اتوماسیون | تسک‌ها | گردش‌کار | Custom Projects، MCP [ت] |

## C. خلاصه صفحات (Builder مهم‌ترین)

تب‌های Builder: **What to build** (حالت Build، بلوک‌ها، قیود ساختاری مثل Max tree depth) · **Data** (نماد/TF، Precision، تقسیم IS/OOS، هزینه‌ها) · **Trading options** (SL/TP، جهت، حداکثر معاملات) · **Genetic options** (نسل‌ها، Population، نرخ جهش/تلاقی، Island+migration، Initial population conditions، Decimation) · **Ranking** (Databank size، فیلتر «keep only that fit»، Fitness وزنی با Minimize/Maximize/Approximate از بیلد ۱۳۰) · **Cross checks** (اسلایدر ساده یا تک‌تک در Full Settings) · **Money management**.

نکات رفتاری مهم:
- **Initial population conditions ≠ Ranking filters**: شرط‌های فیلتر نباید روی جمعیت اولیه اعمال شوند [ت: گزارش باگ]. سخت‌گیری بیش‌ازحد = نسل اول ساخته نمی‌شود [ت].
- **Decimation**: X برابر بیشتر تولید می‌شود تا فیلترشده‌ها پر شوند [ت].
- سایر صفحات: Retester، Optimizer (WF)، Improver (Mass improve بیلد ۱۳۰)، Custom Projects، Data manager، Portfolio، Code Editor (Java/JAR [ت])، AlgoWizard (بازنویسی بیلد ۱۴۳ [ت])، MCP (بیلد ۱۴۴ [ت]).

## D. خط لوله Builder (گام‌به‌گام)

۱ آماده‌سازی داده ← ۲ تقسیم IS/OOS (جلوگیری از leakage) ← ۳ انتخاب بلوک‌ها ← ۴ تنظیم هزینه‌ها ← ۵ شرایط جمعیت اولیه ← ۶ حلقه ژنتیک ← ۷ Ranking ← ۸ قیف Cross-check (فقط بازماندگان) ← ۹ Databank (با seed) ← ۱۰ پورتفوی/صدور.

شبه‌کد ژنتیک [ط]:
```
for island in islands:
    pop = generate until initial_conditions met (with decimation)
    for gen in max_generations:
        fitness = backtest_IS(each individual)
        parents = select(); crossover(p_cx); mutate(p_mut)
        every k gens: migrate(migration_size)
        survivors passing ranking → cross-check funnel → databank
```

## E. تست‌های استحکام

| تست | کشف می‌کند | برچسب |
|---|---|---|
| Higher precision | وابستگی به شبیه‌سازی درون‌کندل | [ت] |
| MC trades manipulation | شانس‌محور بودن منحنی | [ت] |
| Retest on additional markets | تعمیم لبه بین نمادها | [ت] |
| MC retest methods | حساسیت به تغییر داده/پارامتر | [ت] |
| Walk-Forward | پایداری زمانی | [د] |
| SPP | پایداری پارامتری | [د] |
| OOS (multiple periods) | تعمیم‌پذیری | [ت] |

[ط] آستانه عددی هر تست (مثلاً «۹۵٪ شبیه‌سازی MC با DD < X») باید در پیکربندی ذخیره شود.

## F. تولید کد — مرحله اجباری [ط]

**تأیید عددی:** استراتژی صادرشده در Strategy Tester پلتفرم هدف اجرا و CountTrades/PnL/DD با موتور داخلی مقایسه شود؛ تلرانس از پیش تعریف‌شده.

## G. انتخاب فناوری پیشنهادی [ط]

Rust/C++ (یا Python+Numba) هسته · Parquet+DuckDB · ژنتیک سفارشی روی AST · Ray · FastAPI · PostgreSQL (SQLite برای MVP) · React+TS · Jinja2 برای MQL5 · MCP SDK.

مدل داده Databank [ط]:
```
Strategy(id, ast_json, params, seed, data_version, cost_config, build_config_hash, created_at)
Metric(strategy_id, period[IS/OOS], name, value)
CrossCheckResult(strategy_id, test, config, passed, report_blob)
```

## H. نقشه راه ۱۰ فازی [ط]

۱ داده+موتور (تطبیق عددی با MT5) ← ۲ بلوک+AST ← ۳ مولد تصادفی ← ۴ ژنتیک جزیره‌ای ← ۵ Ranking+Databank ← ۶ قیف Cross-check ← ۷ کدزایی MQL5 ← ۸ Workflow+Portfolio ← ۹ UI ← ۱۰ MCP/AI.

## I. جدول شکاف MVP و J. ریسک‌ها

ریسک‌ها: حقوقی (فقط تحلیل رفتاری، بررسی EULA) · آماری (data snooping/چندگانه‌آزمایی — حتی معمار SQX هشدار می‌دهد) · عملیاتی (عدم تطابق زنده) · فنی (کیفیت داده/اندیکاتورها) · عملکردی (جمعیت عقیم).

## K. نکات کلیدی اضافه

ذخیره seed+نسخه داده+هش پیکربندی برای بازتولید · هر استفاده از OOS آن را «بکر» از بین می‌برد · benchmark غیررسمی ~۱۴۰k استراتژی/ساعت [ت: انجمن] · قیمت‌گذاری نسخه‌ها متغیر است [ت].

---

## تطبیق با وضعیت فعلی این مخزن (چرا این سند مهم است؟)

| مفهوم SQX | معادل فعلی در مخزن | شکاف |
|---|---|---|
| فنل تست ارزان→گران | `scripts/a3_grid.py` (گرید کوچک پیش‌ثبت‌شده) + gates PSR/DSR/PBO | ❌ مولد استراتژی وجود ندارد؛ فعلاً فقط یک مدل ثابت ارزیابی می‌شود |
| Databank با seed/hash | `validation/ledger.py` (append-only + hash chain) ✅ | ⚠️ ledger موجود است ولی ast_json/params ندارد |
| OOS بکر / جلوگیری از leakage | pre-registration (charter v3) + split deterministic ✅ | ⚠️ هر نگاه به OOS باید در ledger ثبت شود |
| Monte Carlo / Re-test | `stage8/montecarlo.py` (GAP-005: P(profit)=0%) ✅ | تطابق خوب |
| Walk-Forward / WF-OOS | `time_series_validation.py` (purged CV) ✅ | تطابق خوب |
| Ranking/Fitness وزنی | gate های `validation/gates.py` | ⚠️ fitness وزنی چندمعیاره نداریم |
| Islands/Genetic builder | — | ❌ خارج از دامنه فعلی (نیازمند تأیید انسانی برای تغییر فاز) |
| تأیید عددی کدزایی | — | ❌ فعلاً کدزایی نداریم (research/paper-only طبق Charter) |

**تصمیم ثبت‌شده [طبق ADL]:** این سند به‌عنوان blueprint مرجع برای فاز بعدی («Research Factory» — تولید انبوه پیکربندی + قیف اعتبارسنجی) استفاده می‌شود؛ اما چون مرز Charter «تحقیق/اوراق قهرمانی» است، هیچ اجرای زنده/کدزایی MT5 در دستور کار نیست. اولین گام قابل اجرا همان A3 است: گرید پیش‌ثبت‌شده روی داده واقعی با فنل ارزان→گران (cost model → metrics → gates → ledger).

## مرحله بعد (پیشنهاد سند کاربر)

دو گزینه باز: (۱) جدول کامل هر کنترل Builder (نام/نوع/پیش‌فرض/اثر) — نیازمند Trial ۱۴ روزه کاربر؛ (۲) طراحی کامل AST و موتور ژنتیک با کد نمونه — قابل انجام در مخزن، در شاخه جدا و صرفاً research-only.
