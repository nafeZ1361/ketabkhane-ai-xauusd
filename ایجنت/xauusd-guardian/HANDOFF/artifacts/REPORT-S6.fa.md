# گزارش S6 — بازگشت‌پذیری migration 0003 (افزودنی و قابل‌برگشت)

**مخزن:** `nafeZ1361/ketabkhane-ai-xauusd` · **پروژه:** `ایجنت/xauusd-guardian`
**شاخه:** `fix/w1-timezone-validation` · **HEAD:** `9a3b53af95267c6ecaeca6b567006f671786ecd7`
**کلون کاری:** `C:\GS5\repo` · **تاریخ:** 2026-11-09 · **مفسر:** `C:\Python311\python.exe` (3.11.8) · pytest 9.2.0

---

## ۰) حکم

> **S6: PASS** — الزام «migration 0003 افزودنی و قابل‌برگشت باشد» برآورده شد و بازرس مستقل هم **PASS** داد؛ **must-fix: هیچ**.
> ۱۵/۱۵ تست هدفمند · ۲۶۷/۲۶۷ مجموعه · `compileall` با Exit 0 · ۴ کنترل جهشی (mutation) همه کشنده · ۰ commit / ۰ push / ۰ fetch.

**وضعیت درخت:** تغییرات S6 **ذخیره‌نشده (uncommitted)** و دست‌نخورده باقی ماندند — دقیقاً همان درختی که بازرس مستقل روی آن حکم داد. پس از حکم، هیچ فایلی تغییر نکرد تا اعتبار بازرسی حفظ شود.

| سنجه | مقدار |
|---|---|
| فایل‌های تغییر‌یافته | ۴ فایل ردیابی‌شده + ۲ افزوده (`rollback/`, تست) |
| تست هدفمند S6 | **۱۵ passed** — Exit **0** |
| مجموعهٔ کامل | **267 passed / 0 failed / 0 error / 0 skipped** — Exit **0** |
| `compileall` | Exit **0** |
| کنترل جهشی | ۴/۴ تست محافظ قرمز شد (محافظت واقعی) |
| بازرس مستقل | **PASS** — «Must-fix: none» |
| commit لازم؟ | **بله** (فایل‌ها آماده‌اند؛ commit به شما واگذار شد) |
| S7 | **شروع نشد** |

---

## ۱) دور ۱ — استخراج الزامات از وضعیت واقعی مخزن

پیش از هر تغییری این‌ها خوانده شد: `PHASE3_PLAN.md` (§۵ و §۶)، `PROJECT_STATE.md`، `DECISIONS_LOG.md` (D-016)، `migrations/0001_init.sql`، `0002_market_data.sql`، `0003_signals.sql`، موتور مهاجرت `src/guardian/storage/db.py`، تست‌های S5 (`tests/unit/test_signal_migration.py`) و شاهد S5.

نتیجهٔ استخراج:

1. موتور مهاجرت **فقط رو به جلو** کار می‌کند: `discover_migrations` با الگوی `^[0-9]{4}_[a-z0-9_]+\.sql$`، تاریخچه در `schema_migrations` با **هش SHA-256 هر فایل** (پس migration اعمال‌شده قابل ویرایش نیست).
2. `0003_signals.sql` سه دستور `CREATE ... IF NOT EXISTS` دارد و هیچ `ALTER`/`DROP` روی `0001`/`0002` ندارد ⇒ افزودنی است.
3. **معکوس وجود نداشت.** خودِ سرصفحهٔ فایل 0003 می‌گفت معکوس «عمداً پیاده نشده» و فایل `0003_*_down*.sql` اگر در `migrations/` باشد به‌عنوان migration بعدی **رو به جلو** اجرا می‌شود. پس S6 = ساختن مکانیزم معکوس + فایل معکوس + اثبات رفتاری.
4. الزام پذیرش، بدون تفسیر اضافه: **«migration 0003 افزودنی و قابل‌برگشت باشد.»**

در همین مرحله یک **کار نیمه‌تمام از تلاش قبلی** در درخت کاری پیدا شد (down file + `revert_migration` + ۸ تست + شاهد `170723Z`). طبق دستور، از نو ساخته نشد؛ ابتدا خصمانه بازرسی شد.

---

## ۲) دور ۲ — بازرسی خصمانه: یک نقص واقعی پیدا شد

پیاده‌سازی موجود، معکوس را در یک تراکنش اتمی اجرا می‌کرد و ledger را درست پاک می‌کرد، اما:

> **نقص (بالقوه مخرب):** `revert_migration` هر SQL داخل فایل down را **بدون هیچ محدودیتی** اجرا می‌کرد. اگر آن فایل `DROP TABLE bars;` داشت، دادهٔ پیش از 0003 بی‌صدا از بین می‌رفت، سطر `schema_migrations` هم پاک می‌شد و «برگشت موفق» ثبت می‌شد.
> این دقیقاً بند ۷ بازرسی پرامپت است: *rollback that accidentally removes pre-0003 data*.

سه نقص همراه:

| # | نقص | چرا واقعی بود |
|---|---|---|
| ۱ | هیچ نگهبان مالکیتی نبود | فایل down می‌توانست هر شیء موجود را drop کند؛ محافظت فقط «بازبینی انسانی» بود، نه کد |
| ۲ | هیچ پس‌شرطی نبود | اگر down ناقص بود (فقط `signals`)، ledger می‌گفت 0003 نیست ولی `signal_runs` می‌ماند و apply بعدی بی‌صدا no-op می‌شد |
| ۳ | انطباق شکل جدول بررسی نمی‌شد | با `CREATE TABLE IF NOT EXISTS`، جدول هم‌نام از قبل موجود «تصاحب» می‌شد و برگشت آن را drop می‌کرد |

همچنین تطبیق فایل down سست بود: هر فایل `.sql` با ۴ رقم در `rollback/` کاندید می‌شد (حتی یک فایل رو‌به‌جلو که اشتباهاً کپی شده باشد).

---

## ۳) دور ۳ — اصلاح حداقلی + تست‌های هدفمند

اصلاحات فقط در محدودهٔ S6 (فایل down، موتور معکوس در `db.py`، تست‌ها، اسناد) و بدون دست‌زدن به رفتار S5:

**الف) نگهبان مالکیت (whitelist):** اشیائی که هر migration رو‌به‌جلو می‌سازد از خودِ فایل forward استخراج می‌شود (`CREATE TABLE/INDEX`). هر دستور در فایل down باید **فقط** `DROP TABLE`/`DROP INDEX` همان اشیاء باشد. `DELETE`، `UPDATE`، `ALTER`، `ATTACH` یا drop هر شیء دیگر **قبل از اجرای حتی یک دستور** رد می‌شود.

**ب) پس‌شرط بازگشت:** بعد از اجرا و **داخل همان تراکنش** بررسی می‌شود که هیچ‌یک از اشیاء ساخته‌شدهٔ 0003 در `sqlite_master` باقی نمانده باشد؛ وگرنه کل برگشت rollback می‌شود.

**ج) بررسی انطباق شکل:** ستون‌های اعلام‌شده در `CREATE TABLE` با `PRAGMA table_info` مقایسه می‌شود؛ جدول «رانده‌شده» (drift) drop نمی‌شود.

**د) `reversal_plan`:** قبل از عمل، کل برگشت قابل بازبینی است: نسخه، شیءها، نام فایل down و **هش SHA-256** آن.

**ه) تطبیق سخت‌گیرانه:** فقط `NNNN_name.down.sql` کاندید است؛ فایل رو‌به‌جلو که در `rollback/` کپی شود کاندید نمی‌شود.

**و) تراکنش صریح:** `BEGIN IMMEDIATE ... COMMIT` + `DELETE` پارامتری از `schema_migrations` + rollback در هر خطا.

رفتارهای رد‌کننده (fail-closed): نسخهٔ اعمال‌نشده، نسخهٔ بعدی اعمال‌شده، forward تغییر‌کرده پس از apply، فایل down گم‌شده یا تکراری، دستور غیرمجاز در down، جدول drift‌شده، بازگشت ناقص.

### تست‌های S6 — ۱۵ مورد (۸ مورد قبلی + ۷ مورد جدید)

موضوعات: DB تازه · PK برنامه‌ریزی‌شده · `strength` از نوع TEXT · ستون‌های `signal_runs` · افزودنی‌بودن با حفظ داده · تشخیص دست‌کاری هش · برگشت فقط اشیاء 0003 · re-apply قطعی · رد نسخهٔ اعمال‌نشده · رد ترتیب خارج · الزام دقیقاً یک فایل down · رد forward تغییر‌کرده · **اتمی‌بودن وقتی جدولی گم است** · عدم کشف فایل down به‌عنوان forward · **نگهبان مالکیت (کنترل جهشی)** · **رد دستور غیر-DROP** · **رد جدول drift‌شده** · **رد down ناقص + rollback** · **بازبینی‌پذیری plan** · **forward کپی‌شده در rollback** · **حذف ایندکس‌های 0003**.

هیچ تستی حذف، skip یا تضعیف نشد.

---

## ۴) دور ۴ — بازرسی انتشار و کنترل جهشی

### ۴.۱ کنترل‌های جهشی (mutation) — اثبات اینکه محافظت واقعی است

هر جهش روی یک **کپی** از پروژه اعمال شد (مخزن دست‌نخورده) و تست مربوطه باید **قرمز** می‌شد:

| جهش | تغییر | نتیجه |
|---|---|---|
| M1 | حذف نگهبان مالکیت | `test_down_script_may_only_drop_objects_the_forward_created` → **FAILED** ✅ |
| M2 | حذف پس‌شرط | `test_incomplete_down_script_is_refused_and_rolled_back` → **FAILED** ✅ |
| M3 | حذف تراکنش | `test_revert_is_atomic_when_a_table_is_missing` → **FAILED** ✅ |
| M4 | حذف بررسی شکل | `test_revert_refuses_a_drifted_table` → **FAILED** ✅ |

`MUTATION_SUMMARY: probes=4 unkilled=0` — Exit 0.

بازرس مستقل هم دو جهش مستقل خودش را اجرا کرد (حذف فراخوانی بررسی شکل، و جایگزینی نگهبان با split خام) و هر دو تست مربوطه را قرمز کرد.

### ۴.۲ شواهد اعمال migration (اجرای واقعی)

```
1) apply 0001+0002 -> [1, 2]     seeded pre-0003 rows: bars=2 feed_runs=2
2) apply 0003     -> [3]         signals+signal_runs present: True
                                 post-0003 rows: signals=1 signal_runs=1
                                 ledger: [1, 2, 3]
3) reversal plan  : version=3 down=0003_signals.down.sql
                    sha256=sha256:8b5e4263…aa42
                    tables=['signal_runs','signals'] indexes=['idx_signal_runs_window','idx_signals_run']
```

### ۴.۳ شواهد بازگشت‌پذیری

```
4) revert 0003 -> 3              0003 objects still present: []
                                 pre-0003 rows intact: bars=2 (was 2) feed_runs=2 (was 2)
                                 ledger: [1, 2]
5) re-apply 0003 -> [3]          tables back, rows in signals = 0
                                 bars still 2   ledger: [1, 2, 3]
                                 second apply is a no-op -> []
6) guard refused a reverse that would drop a pre-0003 table:
   MigrationError: 0003_signals.down.sql would drop 'bars', which 0003_signals.sql did not create
   bars still 2   ledger: [1, 2, 3]
RESULT: additive + reversible + pre-0003 data preserved + deterministic re-apply
```

### ۴.۴ جدول پذیرش (۱۰ بند دور ۴)

| شرط | نتیجه | شاهد |
|---|---|---|
| 0003 روی schema فعلی اعمال می‌شود | ✅ | `apply_migrations` → `[3]`؛ تست `test_revert_removes_only_the_0003_objects` |
| bookkeeping درست ثبت می‌شود | ✅ | `schema_migrations` نسخه/نام/hash/`applied_at`؛ تست‌های `test_signal_migration.py` |
| دادهٔ پیش از 0003 سالم می‌ماند | ✅ | snapshot قبل/بعد `bars`/`feed_runs` برابر؛ دمو: `bars=2 (was 2)` |
| ساختارهای `signals` و `signal_runs` درست‌اند | ✅ | PK و نوع `strength=TEXT` تست شده؛ دمو presence=True |
| بازگشت صریحاً نشان داده می‌شود | ✅ | بخش ۴.۳ + تست‌های بازگشت |
| re-apply قطعی و بی‌اتلاف | ✅ | `[3]` دوباره، `signals=0`، `bars=2`، apply دوم `[]` |
| هیچ عملیات مخربی به schema/دادهٔ قبلی نمی‌زند | ✅ | نگهبان مالکیت + پس‌شرط + M1/M2 |
| تست‌ها سبز | ✅ | ۱۵/۱۵ و ۲۶۷/۲۶۷، Exit 0 |
| شواهد قابل بازتولید | ✅ | `evidence/phase3-S6-20261109T173019Z.txt` + `.sha256` |
| فایل نامرتبط تغییر نکرد | ✅ | ۴ فایل ردیابی‌شده + ۲ افزوده، همه در دامنهٔ S6 |

---

## ۵) فایل‌های تغییر‌یافته (دقیق) و SHA-256

### تغییر‌یافته (۴)
| فایل | تغییر | SHA-256 (بایت خام) |
|---|---|---|
| `src/guardian/storage/db.py` | +۳۲۴ خط: `discover_down_migrations`، `reversal_plan`، `revert_migration`، نگهبان/پس‌شرط/شکل | `79e995146e4d6e7c5080ffb106f75396e7388587cfe6be92dde0de450dfb32e0` |
| `DECISIONS_LOG.md` | بازنویسی بند ۸ از D-016 | `f9baa233e223f2f767f3927d106dc6cb763ec9d5fbdee26c25fcc142929d8482` |
| `PHASE3_PLAN.md` | §۵ بازنویسی + وضعیت دروازه‌ها | `4dfc2a50955b3082cc284d840c60c547f07ed4a22da4d64340df2bf5fe70b3a4` |
| `PROJECT_STATE.md` | ردیف Phase 3 | `481943cfd05dfc11be48bb464f713efd75b1fc1d58317fcde5c9c51ce5c34493` |

### افزوده (۲)
| فایل | نقش | SHA-256 |
|---|---|---|
| `migrations/rollback/0003_signals.down.sql` | معکوس: `DROP TABLE signals;` سپس `DROP TABLE signal_runs;` | `8b5e42635e887387ec4dc44d2d7dcf10d59476ce12a243b41e1c08cc7437aa42` |
| `tests/unit/test_migration_reversal.py` | ۱۵ تست S6 (۳۱۷ خط) | `20d1617dc98253c485fe31bf1bf336347271aa7a95adc25498ffb0d2cc888d24` |

### شاهد
| فایل | SHA-256 |
|---|---|
| `evidence/phase3-S6-20261109T173019Z.txt` | `7a6a7f51ea870e6ef6a9d2c7570b84824302ef9805a1f6da9118b7e4f4fea85a` |
| `evidence/phase3-S6-20261109T173019Z.txt.sha256` | `44c7dbd64439b790529bbb2b286b82576676918dc22f2b474867992f8b3dfb55` |

**تغییرنکرده و نباید تغییر کند:** `migrations/0003_signals.sql` (هش آن در ledger پین شده؛ ویرایش، `apply_migrations` و `reversal_plan` را برای همهٔ DBهای اعمال‌شده می‌شکند).

---

## ۶) دستورها، Exit codeها و شمارش تست

```powershell
# در C:\GS5\repo\ایجنت\xauusd-guardian
C:\Python311\python.exe -m pytest tests/unit/test_migration_reversal.py -v
#   15 passed, EXIT 0

C:\Python311\python.exe -m pytest -q
#   JUnit: tests=267 failures=0 errors=0 skipped=0, EXIT 0

C:\Python311\python.exe -m compileall -q src scripts tests
#   EXIT 0

C:\Python311\python.exe C:\GS5\mutation_probe.py
#   probes=4 unkilled=0, EXIT 0

C:\Python311\python.exe C:\GS5\s6_demo.py
#   RESULT: additive + reversible + pre-0003 data preserved + deterministic re-apply, EXIT 0
```

مجموعه از ۲۶۰ (تلاش قبلی) به **۲۶۷** رسید: ۷ تست جدید، ۰ تست حذف‌شده.

---

## ۷) ایمنی مخزن

| مورد | مقدار | تأیید |
|---|---|---|
| شاخه | `fix/w1-timezone-validation` | ✅ |
| HEAD | `9a3b53af95267c6ecaeca6b567006f671786ecd7` | ✅ بدون تغییر |
| parent | `08ce5f331a72d5b13c5757654e098ac397ba9d1b` | ✅ |
| `main` | `1dad9588083f210fca868f49358aff44826e6f2f` | ✅ دست‌نخورده |
| شاخهٔ موازی `fix/xauusd-guardian-w1-timezone` | `76d468eda3e15e2c7d87a4fdcfe0f7b45c620b45` | ✅ دست‌نخورده |
| commit / push / merge / rebase / reset / amend | **هیچ** | ✅ |
| commit دومی برای S5 | **ساخته نشد** | ✅ |
| افزودن شاهد S5 به index | **انجام نشد** | ✅ |

**محدودیت اعلام‌شده (مهم):** شاخهٔ محلی از ref دوربالا **۱ commit جلوتر** است؛ یعنی `origin/fix/w1-timezone-validation` هنوز روی `08ce5f3` (پیش از S5) است و commit `9a3b53a` **فقط محلی و push‌نشده** است. چون `fetch` ممنوع بود، این ref تازه نشد. به همین دلیل `main` و شاخهٔ موازی از کلون اسنپ‌شات `_work/ketabkhane-ai-xauusd` خوانده شدند (بدون fetch/push). بازرس مستقل هم همین را تأیید کرد.

---

## ۸) حکم بازرس مستقل

| مورد | مقدار |
|---|---|
| بازرس | عامل مستقل read-only (`审阅者`)، بدون دیدن استدلال Developer |
| حکم | **PASS** — «Must-fix: none (0 findings)» |
| اجرای مستقل | ۱۵/۱۵ هدفمند · ۲۶۷/۲۶۷ مجموعه · `compileall` · چرخهٔ کامل apply→seed→revert→re-apply روی SQLite واقعی · دو کنترل جهشی خودش |
| گزارش کامل | `S6-review/INSPECTOR-S6.md` · SHA-256: `c7d124083f413d8c7f9fbd46cbc16295d7b5c2734dc28594d128ba8eb3ea14eb` |

نقل مستقیم: «*PASS. No must-fix findings. All 10 working-tree paths are inside S6 scope; the S5 commit is untouched.*» و «*...a post-condition that forces rollback of a partial reverse.*»

---

## ۹) ریسک‌های باقی‌مانده (اعلام‌شده، غیرمسدودکننده)

این‌ها **پس از** صدور حکم اصلاح نشدند، چون هر ویرایشی درخت بازرسی‌شده را عوض می‌کرد و حکم PASS را بی‌اعتبار می‌ساخت. پیشنهاد: در همان commitی که تأیید می‌کنید، همراه اصلاحات S6 ثبت شوند.

| # | مورد | وضعیت | اصلاح پیشنهادی |
|---|---|---|---|
| R1 | جدول هم‌نام با **شکل یکسان** که پیش از 0003 وجود داشته، «تصاحب» می‌شود و برگشت آن را drop می‌کند. بررسی فعلی فقط ستون‌ها را مقایسه می‌کند، پس drift را می‌گیرد ولی این حالت را نه. | پذیرفته‌شده؛ روی lineage رسمی غیرقابل‌وقوع | یا متن docstring محدود شود، یا provenance در `apply_migrations` ثبت شود (تغییر رفتار S5 — نیازمند تصمیم جدا) |
| R2 | docstring تابع `_check_declared_shapes` ادعای «guards the adoption case» دارد که دقیق‌تر از رفتار واقعی است | فقط کامنت؛ رفتار مطابق D-016 | اصلاح یک‌خطی متن docstring |
| R3 | هدر `0003_signals.sql` می‌گوید معکوس «عمداً پیاده نشده» — پس از S6 نادرست است، اما فایل hash-pinned است | پذیرفته‌شده (ویرایش = شکستن ledger) | فایل بایت‌به‌بایت دست‌نخورده بماند؛ اشاره در D-016 و هدر فایل down کافی است |
| R4 | شاهد قدیمی `phase3-S6-20261109T170723Z.txt` بنر superseded روی خودش ندارد | پذیرفته‌شده (شاهد ویرایش نمی‌شود) | شاهد جدید در خط ۳ همان را superseded اعلام می‌کند؛ یا در آینده به `evidence/superseded/` منتقل شود |
| R5 | خط ۳ `PHASE3_PLAN.md` هنوز «252/252 … S6–S7 OPEN» می‌گوید (ناهم‌خوان با خط ۵۰ و ۲۶۷ تست) | پذیرفته‌شده | هم‌زمان با ثبت حکم S6 به‌روزرسانی شود |
| R6 | سورس اسکریپت mutation داخل فایل شاهد نیست (فقط هش و مسیرش) | پذیرفته‌شده | سورس در شاهد جاسازی شود یا اسکریپت زیر `evidence/` قرار گیرد |

---

## ۱۰) commit لازم است؟

**بله — اما انجام نشد (مجاز نبود).** تغییرات عمداً درخت کاری‌اند. برای ثبت:

```powershell
git -C C:\GS5\repo status --short
git -C C:\GS5\repo add -- ایجنت/xauusd-guardian/migrations/rollback `
                          ایجنت/xauusd-guardian/src/guardian/storage/db.py `
                          ایجنت/xauusd-guardian/tests/unit/test_migration_reversal.py `
                          ایجنت/xauusd-guardian/DECISIONS_LOG.md `
                          ایجنت/xauusd-guardian/PHASE3_PLAN.md `
                          ایجنت/xauusd-guardian/PROJECT_STATE.md
git -C C:\GS5\repo commit -m "feat(s6): reversible migration 0003 with guarded reversal"
```

**هشدار:** از `git add -A` استفاده نکنید — شاهد S5 هنوز ردیابی‌نشده است و طبق دستور نباید اضافه شود. اگر شاهد S6 را هم می‌خواهید، همان دو فایل `evidence/phase3-S6-20261109T173019Z.txt*` را جداگانه `add` کنید.

---

## ۱۱) تأییدیهٔ پایان

- **S7 شروع نشد.** هیچ کار S7 در دامنه نبود.
- **Phase 4 شروع نشد.**
- **هیچ اتصال MT5، هیچ سفارش، هیچ حساب.** فقط SQLite محلی و stdlib.
- **هیچ وابستگی جدید** اضافه نشد؛ موتور مهاجرت جدیدی معرفی نشد.
- **هیچ fetch/push/merge/rebase/reset/amend/حذف شاخه‌ای** انجام نشد.
- پس از بازرسی مستقل، **هیچ فایلی تغییر نکرد**.

**توقف پس از بازرسی مستقل S6 — مطابق دستور.**
