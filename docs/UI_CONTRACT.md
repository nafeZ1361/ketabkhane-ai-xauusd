# Ù‚Ø±Ø§Ø±Ø¯Ø§Ø¯ Ø±Ø§Ø¨Ø· Ú©Ø§Ø±Ø¨Ø±ÛŒ (UI Contract) â€” ÙØ§Ø² A2.1

- Ù†Ø³Ø®Ù‡Ù” API: `1.0`
- ÙˆØ¶Ø¹ÛŒØª: ÙÙ‚Ø· Ø®ÙˆØ§Ù†Ø¯Ù†ÛŒ (read-only)
- Ø¯Ø§Ù…Ù†Ù‡: `127.0.0.1` ÙÙ‚Ø·

## Ù‚ÙˆØ§Ø¹Ø¯ Ø¹Ù…ÙˆÙ…ÛŒ

| Ù…ÙˆØ±Ø¯ | Ù‚Ø§Ø¹Ø¯Ù‡ |
|---|---|
| Ù‚Ø§Ù„Ø¨ | JSON Ø¨Ø§ Ú©Ø¯Ú¯Ø°Ø§Ø±ÛŒ UTF-8 (`Content-Type: application/json; charset=utf-8`) |
| Ù…ØªØ¯ Ù…Ø¬Ø§Ø² | ÙÙ‚Ø· `GET` (Ø³Ø§ÛŒØ± Ù…ØªØ¯Ù‡Ø§ â†’ `405`) |
| Ø²Ù…Ø§Ù† | ISO-8601 Ø¨Ø§ Ù…Ù†Ø·Ù‚Ù‡Ù” Ø²Ù…Ø§Ù†ÛŒ UTC Ùˆ Ù¾Ø³ÙˆÙ†Ø¯ `+00:00` |
| Ù¾ÙˆÙ„ | Ø¯Ù„Ø§Ø± Ø¢Ù…Ø±ÛŒÚ©Ø§ (USD)ØŒ Ø¹Ø¯Ø¯ Ø§Ø¹Ø´Ø§Ø±ÛŒ |
| Ù‚ÛŒÙ…Øª | ÙˆØ§Ø­Ø¯ Ø§Ø±Ø² Ù…Ø¸Ù†Ù‡ (Ø¨Ø±Ø§ÛŒ XAUUSD: Ø¯Ù„Ø§Ø± Ø¨Ø± Ø§ÙˆÙ†Ø³) |
| point | Ø¹Ø¯Ø¯ ØµØ­ÛŒØ­ |
| Ù†Ø³Ø®Ù‡ | Ù‡Ø± Ù¾Ø§Ø³Ø® Ù…ÙˆÙÙ‚ Ø´Ø§Ù…Ù„ `api_version` Ø§Ø³Øª |

## 1) `GET /health`

Ù¾Ø§Ø³Ø® `200`:

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

| ÙÛŒÙ„Ø¯ | Ù†ÙˆØ¹ | Ù…Ø¹Ù†Ø§ |
|---|---|---|
| `status` | string | Ù‡Ù…ÛŒØ´Ù‡ `ok` Ø¯Ø± Ù¾Ø§Ø³Ø® Ù…ÙˆÙÙ‚ |
| `package_version` | string | Ù†Ø³Ø®Ù‡Ù” Ù¾Ú©ÛŒØ¬ Ù¾Ø±ÙˆÚ˜Ù‡ |
| `time_utc` | string | Ø²Ù…Ø§Ù† Ø³Ø±ÙˆØ± Ø¯Ø± Ù„Ø­Ø¸Ù‡Ù” Ù¾Ø§Ø³Ø® |
| `checks.data_audit_present` | bool | ÙˆØ¬ÙˆØ¯ ÙØ§ÛŒÙ„ Ù…Ù…ÛŒØ²ÛŒ Ø¯Ø§Ø¯Ù‡ |

## 2) `GET /quality`

Ù¾Ø§Ø³Ø® `200`:

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

| ÙÛŒÙ„Ø¯ | Ù†ÙˆØ¹ | Ù…Ø¹Ù†Ø§ |
|---|---|---|
| `source.sha256` | string | Ù‡Ø´ ÙØ§ÛŒÙ„ Ù…Ù…ÛŒØ²ÛŒ Ú©Ù‡ Ø§ÛŒÙ† Ù¾Ø§Ø³Ø® Ø§Ø² Ø¢Ù† Ø³Ø§Ø®ØªÙ‡ Ø´Ø¯Ù‡ |
| `dataset.time_reference` | string | `SERVER_TIME_NAIVE` ÛŒØ¹Ù†ÛŒ Ø²Ù…Ø§Ù†â€ŒÙ‡Ø§ Ø¨Ù‡ ÙˆÙ‚Øª Ø³Ø±ÙˆØ± Ø¨Ø±ÙˆÚ©Ø± Ùˆ Ø¨Ø¯ÙˆÙ† Ù…Ù†Ø·Ù‚Ù‡Ù” Ø²Ù…Ø§Ù†ÛŒâ€ŒØ§Ù†Ø¯ (ØªØ¨Ø¯ÛŒÙ„ Ø¨Ù‡ UTC Ø¯Ø± Ù…ÙˆØªÙˆØ± Ø§Ù†Ø¬Ø§Ù… Ù…ÛŒâ€ŒØ´ÙˆØ¯) |
| `dataset.first_time` / `last_time` | string | ISO-8601 Ø¨Ø¯ÙˆÙ† offset (Ú†ÙˆÙ† Ù…Ø¨Ø¯Ø£ Ø³Ø±ÙˆØ± Ø§Ø³Øª) |
| `integrity.*` | int | Ø´Ù…Ø§Ø±Ø´ Ø®Ø·Ø§Ù‡Ø§Ø› ØµÙØ± = Ø³Ø§Ù„Ù… |
| `zeros.*` | int | ØªØ¹Ø¯Ø§Ø¯ Ù…Ù‚Ø§Ø¯ÛŒØ± ØµÙØ± Ø¯Ø± Ø³ØªÙˆÙ†â€ŒÙ‡Ø§ |
| `gaps.bar_interval_seconds` | int | ÙØ§ØµÙ„Ù‡Ù” ØºØ§Ù„Ø¨ Ú©Ù†Ø¯Ù„â€ŒÙ‡Ø§ |
| `gaps.largest` | array | Û±Û° Ø´Ú©Ø§Ù Ø¨Ø²Ø±Ú¯ |

## 3) Ø®Ø·Ø§Ù‡Ø§

Ù‚Ø§Ù„Ø¨ ÛŒÚ©Ø³Ø§Ù† Ø¨Ø±Ø§ÛŒ Ù‡Ù…Ù‡Ù” Ø®Ø·Ø§Ù‡Ø§:

```json
{
  "api_version": "1.0",
  "error": {"status": 404, "code": "NOT_FOUND", "message": "no route for GET /nope"}
}
```

| Ú©Ø¯ | HTTP | Ù…Ø¹Ù†Ø§ |
|---|---|---|
| `NOT_FOUND` | 404 | Ù…Ø³ÛŒØ± ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø±Ø¯ |
| `METHOD_NOT_ALLOWED` | 405 | Ù…ØªØ¯ ØºÛŒØ± Ø§Ø² GET |
| `AUDIT_MISSING` | 503 | ÙØ§ÛŒÙ„ `docs/evidence/data_audit.json` Ù…ÙˆØ¬ÙˆØ¯ Ù†ÛŒØ³Øª |

## 4) Ø§Ù…Ù†ÛŒØª

- Ø³Ø±ÙˆØ± ÙÙ‚Ø· Ø±ÙˆÛŒ `127.0.0.1` Ú¯ÙˆØ´ Ù…ÛŒâ€ŒØ¯Ù‡Ø¯Ø› Ø±ÙˆÛŒ Ø´Ø¨Ú©Ù‡Ù” Ù…Ø­Ù„ÛŒ Ù…Ù†ØªØ´Ø± Ù†Ù…ÛŒâ€ŒØ´ÙˆØ¯.
- Ù‡ÛŒÚ† Ù†ÙˆØ´ØªÙ†ØŒ Ø¢Ù¾Ù„ÙˆØ¯ ÛŒØ§ Ø§Ø¬Ø±Ø§ÛŒ ÙØ±Ù…Ø§Ù†ÛŒ ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø±Ø¯.
- Ù¾Ø§Ø³Ø®â€ŒÙ‡Ø§ `Cache-Control: no-store` Ø¯Ø§Ø±Ù†Ø¯.

## 5) Ø®Ø§Ø±Ø¬ Ø§Ø² Ø¯Ø§Ù…Ù†Ù‡Ù” A2.1

- ÙØ±Ù… Ø§Ø¬Ø±Ø§ÛŒ Ø¢Ø²Ù…Ø§ÛŒØ´ØŒ ØµÙØ­Ù‡Ù” Ù†ØªØ§ÛŒØ¬ Ùˆ Ù‡Ø± Ø¹Ù…Ù„ÛŒØ§Øª Ù†ÙˆØ´ØªÙ†ÛŒ â†’ ÙØ§Ø² A2.2 Ùˆ A2.3.
## 6) `GET /` â€” ØµÙØ­Ù‡Ù” Ø§Ø¬Ø±Ø§ (A2.2)

Ù¾Ø§Ø³Ø® `200` Ø¨Ø§ `Content-Type: text/html; charset=utf-8`: ÙØ±Ù… Ø³Ø§Ø¯Ù‡Ù” HTML/JS Ø¨Ø¯ÙˆÙ† ÙØ±ÛŒÙ…â€ŒÙˆØ±Ú©ØŒ Ø´Ø§Ù…Ù„ Ù„ÛŒØ³Øª Ø¯Ø§Ø¯Ù‡â€ŒÙ‡Ø§ØŒ Ø§Ø³ØªØ±Ø§ØªÚ˜ÛŒâ€ŒÙ‡Ø§ Ùˆ Ù¾Ø±ÙˆÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ù‡Ø²ÛŒÙ†Ù‡. ØµÙØ­Ù‡ Ø¨Ø§ `fetch` Ø¨Ù‡ `POST /runs` Ùˆ `GET /runs/{id}` ÙˆØµÙ„ Ù…ÛŒâ€ŒØ´ÙˆØ¯.

## 7) `GET /datasets`

Ù¾Ø§Ø³Ø® `200`:

```json
{"api_version": "1.0", "datasets": [{"name": "sample_300k.tsv", "bytes": 19300647}]}
```

ÙÙ‚Ø· ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ù…Ø³ØªÙ‚ÛŒÙ… Ø¯Ø§Ø®Ù„ `data/` Ø¨Ø§ Ù¾Ø³ÙˆÙ†Ø¯ `csv`ØŒ `tsv` ÛŒØ§ `txt`.

## 8) `POST /runs`

Ø¨Ø¯Ù†Ù‡Ù” JSON (Ø­Ø¯Ø§Ú©Ø«Ø± Û¸ Ú©ÛŒÙ„ÙˆØ¨Ø§ÛŒØª):

```json
{"dataset": "sample_300k.tsv", "strategy": "ma_5_20", "profile": "config/scenario_s1.json", "trend_window": 500}
```

| ÙÛŒÙ„Ø¯ | Ø§Ù„Ø²Ø§Ù…ÛŒ | Ù‚Ø§Ø¹Ø¯Ù‡ |
|---|---|---|
| `dataset` | Ø¨Ù„Ù‡ | ÙÙ‚Ø· Ù†Ø§Ù… ÙØ§ÛŒÙ„ Ø³Ø§Ø¯Ù‡ Ø¯Ø§Ø®Ù„ `data/`Ø› Ø¨Ø¯ÙˆÙ† `/`ØŒ `\` ÛŒØ§ `..` |
| `strategy` | Ø¨Ù„Ù‡ | ÛŒÚ©ÛŒ Ø§Ø² Ø§Ø³ØªØ±Ø§ØªÚ˜ÛŒâ€ŒÙ‡Ø§ÛŒ Ø«Ø¨Øªâ€ŒØ´Ø¯Ù‡ |
| `profile` | Ø®ÛŒØ± | `none` ÛŒØ§ `config/*.json` Ù…ÙˆØ¬ÙˆØ¯ |
| `trend_window` | Ø®ÛŒØ± | Ø¹Ø¯Ø¯ Ø¨ÛŒÙ† Û² Ùˆ Û±Û°Û°Û°Û°Û° |

Ù¾Ø§Ø³Ø® `202`:

```json
{"api_version": "1.0", "run_id": "49b038e5ff14", "status": "QUEUED", "status_url": "/runs/49b038e5ff14"}
```

Ø§Ø¬Ø±Ø§ Ø¯Ø± ÛŒÚ© Thread Ù¾Ø³â€ŒØ²Ù…ÛŒÙ†Ù‡ Ø´Ø±ÙˆØ¹ Ù…ÛŒâ€ŒØ´ÙˆØ¯ Ùˆ ØµÙ Ø¯Ø± Ø­Ø§ÙØ¸Ù‡ Ù†Ú¯Ù‡â€ŒØ¯Ø§Ø±ÛŒ Ù…ÛŒâ€ŒØ´ÙˆØ¯Ø› Ø®Ø±ÙˆØ¬ÛŒ Ø¯Ø± `artifacts/ui_runs/<run_id>/`.

## 9) `GET /runs/{id}`

Ù¾Ø§Ø³Ø® `200`:

```json
{
  "api_version": "1.0",
  "run": {
    "run_id": "49b038e5ff14",
    "status": "COMPLETED",
    "created_at": "2026-10-25T16:20:00+00:00",
    "started_at": "2026-10-25T16:20:00+00:00",
    "finished_at": "2026-10-25T16:20:41+00:00",
    "params": {"dataset": "sample_300k.tsv", "strategy": "ma_5_20", "profile": "config/scenario_s1.json", "trend_window": null},
    "result": {
      "metrics": {"trades": 9890, "net_pnl": -25171.31, "win_rate": 0.33, "profit_factor": 0.98, "max_drawdown": 30000.0},
      "cost_label": "PROVISIONAL_COST_SCENARIO",
      "strategy": "ma_5_20",
      "elapsed_seconds": 40.4,
      "broker_profile": "XAUUSD-AronMarkets-2026-10-s1",
      "artifacts": {"trades_csv": "artifacts/ui_runs/<id>/trades.csv",
                     "summary_json": "artifacts/ui_runs/<id>/summary.json",
                     "manifest_json": "artifacts/ui_runs/<id>/manifest.json"}
    },
    "error": null
  }
}
```

| ÙˆØ¶Ø¹ÛŒØª | Ù…Ø¹Ù†Ø§ |
|---|---|
| `QUEUED` | Ø¯Ø± ØµÙØŒ ØªØ§Ø²Ù‡ Ø«Ø¨Øª Ø´Ø¯Ù‡ |
| `RUNNING` | Ø¯Ø± Ø­Ø§Ù„ Ø§Ø¬Ø±Ø§ |
| `COMPLETED` | ØªÙ…Ø§Ù… Ø´Ø¯Ø› `result` Ù¾Ø± Ø§Ø³Øª |
| `FAILED` | Ø®Ø·Ø§Ø› `error` = `{code, message}` |

Ø¯Ø± `FAILED`ØŒ ÙÛŒÙ„Ø¯ `result` Ø¨Ø±Ø§Ø¨Ø± `null` Ø§Ø³Øª.

## 10) Ú©Ø¯Ù‡Ø§ÛŒ Ø®Ø·Ø§ÛŒ Ø§Ø¶Ø§ÙÙ‡

| Ú©Ø¯ | HTTP | Ù…Ø¹Ù†Ø§ |
|---|---|---|
| `BAD_DATASET` | 400 | Ù†Ø§Ù… ÙØ§ÛŒÙ„ Ù†Ø§Ù…Ø¹ØªØ¨Ø± ÛŒØ§ Ø®Ø§Ø±Ø¬ Ø§Ø² `data/` (Ø´Ø§Ù…Ù„ Path Traversal) |
| `DATASET_NOT_FOUND` | 404 | ÙØ§ÛŒÙ„ Ø¯Ø± `data/` Ù†ÛŒØ³Øª |
| `BAD_STRATEGY` | 400 | Ø§Ø³ØªØ±Ø§ØªÚ˜ÛŒ Ù†Ø§Ø´Ù†Ø§Ø®ØªÙ‡ |
| `BAD_PROFILE` | 400 | Ù¾Ø±ÙˆÙØ§ÛŒÙ„ Ù†Ø§Ù…Ø¹ØªØ¨Ø± ÛŒØ§ Ø®Ø§Ø±Ø¬ Ø§Ø² `config/` |
| `BAD_TREND` | 400 | `trend_window` Ù†Ø§Ù…Ø¹ØªØ¨Ø± |
| `BAD_BODY` | 400 | Ø¨Ø¯Ù†Ù‡Ù” ØºÛŒØ± JSON ÛŒØ§ Ø¨Ø²Ø±Ú¯â€ŒØªØ± Ø§Ø² Û¸ Ú©ÛŒÙ„ÙˆØ¨Ø§ÛŒØª |
| `RUN_NOT_FOUND` | 404 | Ø´Ù†Ø§Ø³Ù‡Ù” Ø§Ø¬Ø±Ø§ ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø±Ø¯ |

## 11) Ø§Ù…Ù†ÛŒØª (Ø¨Ù‡â€ŒØ±ÙˆØ²Ø´Ø¯Ù‡)

- ÙÙ‚Ø· `127.0.0.1`.
- Ù†Ø§Ù… ÙØ§ÛŒÙ„ Ø¯Ø§Ø¯Ù‡ Ø¨Ø§ Ø§Ù„Ú¯ÙˆÛŒ Ù…Ø­Ø¯ÙˆØ¯ Ø§Ø¹ØªØ¨Ø§Ø±Ø³Ù†Ø¬ÛŒ Ùˆ Ù…Ø³ÛŒØ± Ù†Ù‡Ø§ÛŒÛŒ Ø¨Ø§ Ù¾ÙˆØ´Ù‡Ù” `data/` ØªØ·Ø¨ÛŒÙ‚ Ø¯Ø§Ø¯Ù‡ Ù…ÛŒâ€ŒØ´ÙˆØ¯ (Ø¶Ø¯ Path Traversal).
- Ù¾Ø±ÙˆÙØ§ÛŒÙ„ ÙÙ‚Ø· Ø§Ø² `config/*.json` Ù…ÙˆØ¬ÙˆØ¯.
- Ø¨Ø¯Ù†Ù‡Ù” Ø¯Ø±Ø®ÙˆØ§Ø³Øª Ø­Ø¯Ø§Ú©Ø«Ø± Û¸ Ú©ÛŒÙ„ÙˆØ¨Ø§ÛŒØª.
- Ù‡ÛŒÚ† Ø§Ø¬Ø±Ø§ÛŒ ÙØ±Ù…Ø§Ù† Ø³ÛŒØ³ØªÙ…ÛŒ ÛŒØ§ Ø¢Ù¾Ù„ÙˆØ¯ ÙØ§ÛŒÙ„ÛŒ ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø±Ø¯.
