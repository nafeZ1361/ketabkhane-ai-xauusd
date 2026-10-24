# شواهد اجرای سرتاسری (MVP-1)

- تاریخ: 2026-10-25 (Asia/Tehran)
- محیط: `EXEC_ENV_AVAILABLE`
- مفسر اصلی: `Python 3.12.14`
- مفسر محیط تمیز: `Python 3.11.8` (venv تازه، `--without-pip`، بدون هیچ بستهٔ خارجی)

## اجرا روی fixture مصنوعی (۵۰۰ کندل)

    python run_mvp.py run --csv tests/fixtures/synthetic_500.csv --out artifacts/mvp1_run

- کد خروج: 0
- خروجی: OK / trades: 18  net_pnl: -0.26336

## اجرای همان آزمون در venv تمیز

- کد خروج: 0
- خروجی: OK / trades: 18  net_pnl: -0.26336
- SHA-256 یکسان `trades.csv` در هر دو محیط: True

## خروجی نمونه

```json
{
  "strategy": "ma_5_20",
  "fast": 5,
  "slow": 20,
  "cost_label": "NO_TRADING_COSTS",
  "rows": 500,
  "gaps": 0,
  "issues": [],
  "metrics": {
    "trades": 18,
    "net_pnl": -0.26336,
    "win_rate": 0.333333,
    "profit_factor": 0.9861674860288246,
    "max_drawdown": 10.98789
  },
  "input_sha256": "b1613787f47b702103613c050194c9412a97a8c6b52187750dfad725081b2d42"
}
```

## مانیفست (SHA-256 ورودی و خروجی‌ها)

```json
{
  "inputs": [
    {
      "path": "C:\\Users\\icFixer.ir\\Desktop\\ketabkhane-ai-xauusd\\tests\\fixtures\\synthetic_500.csv",
      "sha256": "b1613787f47b702103613c050194c9412a97a8c6b52187750dfad725081b2d42"
    }
  ],
  "outputs": [
    {
      "path": "C:\\Users\\icFixer.ir\\Desktop\\ketabkhane-ai-xauusd\\artifacts\\mvp1_run\\trades.csv",
      "sha256": "2b267fb7dd9d2b9ea7b1161af8572b1e8aaf0c04b4ea0a8af2cad1a75eda33ea"
    },
    {
      "path": "C:\\Users\\icFixer.ir\\Desktop\\ketabkhane-ai-xauusd\\artifacts\\mvp1_run\\summary.json",
      "sha256": "ac36fc34d64e97011c6d36874afdae1a904b0a667b73c50a43343ee317e7615a"
    }
  ]
}
```

## اسکن اسرار

- فایل‌های اسکن‌شده: src, tests, scripts, docs, run_mvp.py, README.md, pyproject.toml, AGENTS.md
- تعداد یافته: 0
- پوشهٔ `legacy/source/` (آرشیو قرنطینه) از اسکن مستثنی است؛ تنها یافتهٔ شناخته‌شدهٔ آن `TOKEN = 'yorToken'` جایگزین است.