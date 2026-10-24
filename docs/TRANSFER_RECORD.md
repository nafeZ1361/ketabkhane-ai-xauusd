# Transfer Record - Legacy Library Import

- Date: 2026-10-25 (Asia/Tehran)
- Source (Windows): `C:\Users\icFixer.ir\Desktop\کتابخونه بخش طلایی1`
- Destination: `legacy/source/` in this repository
- Decision: the user requested that the complete library be transferred to this
  public repository and stay accessible/editable by any AI agent.
- Method: verbatim byte copy. `.gitattributes` sets `legacy/source/** -text`
  so Git never normalizes line endings inside the archive; the SHA-256 values
  below therefore match the repository blobs exactly.
- Excluded: no CSV or market data. The 214 MB XAUUSD CSV stays local under
  `data/` and remains gitignored.
- Status: copy integrity VERIFIED by hash. The code is NOT executed or imported;
  Stage 0 static-review findings still apply.

## Files (14 files, 337561 bytes)

| Path | Bytes | SHA-256 |
|---|---|---|
| backtest/backtester.py | 2116 | 5a74899ab4e5bfba553cbc434f719c91de861cb85210f6f59d314087f9fd2b61 |
| backtest/hashem_backtest.py | 53527 | 332fcd7146b7a2a745e06fa57097f782e9e0d16f2ea5078104f63ef0524634d9 |
| backtest/indicators.py | 40553 | 200caf6d49a786708ba73db72460958f9303edd09b41a8e86dba346dfa322353 |
| backtest/optimizer.py | 17555 | dac90a99585e8697f3663b5ff64222292c41583677b4ac2be9657e444cb11e2c |
| bot.ipynb | 2618 | ca4d65017a9ac47c2e63ce1e9913ef0df33097c3886662cdf40393d075b880b0 |
| module/indicators.py | 105341 | 6f7afb20ea9360c0653ba146531f42ba6e5140342053ea90eb2d7180318ce6b3 |
| module/modifyPosition.py | 4164 | 7adfb64a9fe594fe431ca1d3c053395e944af5d8de81de65970ccb1002f578db |
| module/mt5.py | 42856 | 5972e0361fb4b0534ccbb0f7a9236b9532e264b06b7e2c194eb41ea3e45e022c |
| module/stg.py | 692 | 92182d51ebac7354c0b4f720502a90ad0dd5ab05bb01fc542fa6523ccfa9ce44 |
| module/telegram.py | 3766 | 8f918863b11f2f2a230784ce60689961e1635adc6222815fd93e0855df6c5683 |
| optimizer_results/best_params_XAUUSD._3m_20260819_112418.json | 564 | 1711c00ed3599cc6810fac33c6ee1efece0e923e81f0463a16100ff6e04248ac |
| README.md | 224 | fe3c3e652b30c5a04ea5d7aa9c1ed538bde9619c3be7bf3d7e1b31d0bb091362 |
| smart money indicator.txt | 23341 | 99216698cf44dfb8fecc86a92cae4b30f90141148774ef3eab77fa425d6fb821 |
| TelegramSignal.png | 40244 | 8021210faee09c69cace9f65285e60fdc0069e7328225d63c9ef935bd468db8c |

## Verify

    python scripts/verify_transfer.py

The script re-hashes every archived file and compares it with this table.

## Notes
- Loose `legacy/*` copies that already existed locally remain gitignored;
  this archive is the canonical tracked copy.
- Pre-import secret scan: only placeholder `TOKEN = 'yorToken'` in
  `module/telegram.py`; no live credentials found.