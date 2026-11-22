# 2026-11-22 — D-008 offline dependency closure

- ROLE: Developer (AutoClaw) · ACTOR: `DESKTOP-2NLF7CP\icFixer.ir`
- SCOPE: فقط بستن D-008 (محیط ایزوله + wheelhouse آفلاین + هش‌ها). بدون تغییر رفتار معاملاتی،
  بدون MT5/سفارش، بدون migration، بدون push.
- BASE: HEAD `701a4dd` · worktree شامل تغییرات Graphify ریشه (دست‌نخورده)
- ریشهٔ مشکل: `pip config` آینهٔ مرده `mirror.runflare.com` را pin کرده بود؛ PyPI مستقیم پاسخ می‌داد.
- CHANGED (SHA-256 در شاهد ثبت شده):
  - `requirements.lock` (افزودن `Pygments` + ارجاع به قفل هش‌دار)
  - `requirements-hashed.lock` (۸ توزیع با `--hash=sha256:…`)
  - `WHEELHOUSE.sha256` (۸ wheel)
  - `scripts/build_wheelhouse.py` (بازتولید wheelhouse)
  - `reports/D008-OFFLINE-CLOSURE.md`
  - `DECISIONS_LOG.md` (به‌روزرسانی D-008)، `PROJECT_STATE.md` (بخش D-008)
- ENVIRONMENT: `C:\GuardianD008\venv-d008` (Python 3.11.8، `include-system-site-packages=false`،
  `prefix != base_prefix`)، `C:\GuardianD008\wheelhouse` (۸ wheel، read-only).
- OFFLINE PROOF: `PIP_NO_INDEX=1` + `PIP_INDEX_URL=http://127.0.0.1:1/simple` +
  `pip install --no-index --find-links … --require-hashes` → موفق؛ `pip check` پاک.
- TESTS: `pytest -p no:cacheprovider` با ون D-008 → exit 0، **361 passed**؛ `compileall` exit 0.
- VERDICT: **CLOSED-CANDIDATE** — بازرسی مستقل انجام نشده؛ هیچ PASS اعلام نمی‌شود.
- EVIDENCE: `evidence/d008-closure-20261122T163504Z.txt` — `9d79833bf1776cc277877ef62ce04dda5593271c49c3c87470524f1d197f59fe`
- محدودیت‌های اعلام‌شده: read-only صرفاً attribute است نه ACL؛ wheelها بیرون git می‌مانند
  (numpy 12.6MB > 5MB)؛ `pip list` در این محیط `[]` برمی‌گرداند (مسیر غیرASCII) و نسخه‌ها با
  `importlib.metadata` اثبات شد.
- REMAINING: بازرسی مستقل D-008؛ `PHASE2-CLOCK-RECHECK-1` باز؛ D-019 معوق.
