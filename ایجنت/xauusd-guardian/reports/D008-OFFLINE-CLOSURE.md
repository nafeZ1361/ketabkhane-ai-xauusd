# D-008 — Offline dependency closure (closure candidate, 2026-11-22)

Status: **CLOSED-CANDIDATE** — engineering evidence complete; independent Inspector PASS
is still required (this session does not self-approve).

## 1. Why D-008 existed

`.venv` was created with `--system-site-packages` because `pip install` failed against the
configured mirror `https://mirror.runflare.com/pypi/simple` (`ProxyError`). The environment
therefore inherited packages from `C:\Python311` and was not hermetic.

## 2. What was done

| Step | Result |
|---|---|
| Root cause | `pip config` pins `global.index-url = https://mirror.runflare.com/pypi/simple`, which has no DNS/route on this host. PyPI itself answers (HTTP 200). |
| Venv isolation | `.venv\pyvenv.cfg` has `include-system-site-packages = false`; `sys.prefix != sys.base_prefix`. |
| Closure inventory | Direct: `MetaTrader5`, `pytest`. Transitive: `numpy` (MT5), `pluggy`, `iniconfig`, `packaging`, `colorama`, `Pygments` (pytest). The previous lock omitted `Pygments` — corrected. |
| Pinning | Exact `==` versions for all eight distributions. |
| Wheelhouse | `C:\GuardianD008\wheelhouse` — 8 wheels, `--only-binary=:all:`, downloaded from `https://pypi.org/simple`. Kept **outside the repository** (numpy wheel is 12.6 MB, above the 5 MB commit rule). |
| Hashes | `WHEELHOUSE.sha256` (one line per wheel) and `requirements-hashed.lock` (`--require-hashes` form). Both are committed at the project root. |
| Immutability | Wheel files and both manifests carry the read-only attribute; a write attempt is refused (`UnauthorizedAccessException`). This is an operational guard, not an ACL boundary — the owner can clear the attribute, and that is stated rather than implied. |
| Offline proof | Fresh hermetic venv `C:\GuardianD008\venv-d008` created with `C:\Python311\python.exe -m venv`; install ran with `PIP_NO_INDEX=1` **and** `PIP_INDEX_URL=http://127.0.0.1:1/simple` (unreachable) using `--no-index --find-links <wheelhouse> --require-hashes` → `Successfully installed …`. |
| Verification | `pip check` → “No broken requirements found”; all eight versions match the lock; `sys.prefix` isolated. |
| Suite | `.venv`-independent run from the D-008 venv: **361 passed**, exit 0; `compileall` exit 0. |

## 3. Reproduction (Inspector, read-only)

```powershell
& C:\Python311\python.exe -m venv C:\GuardianD008\venv-check
Get-Content C:\GuardianD008\venv-check\pyvenv.cfg          # include-system-site-packages = false
$env:PIP_NO_INDEX='1'; $env:PIP_INDEX_URL='http://127.0.0.1:1/simple'
& C:\GuardianD008\venv-check\Scripts\python.exe -m pip install --no-index `
    --find-links C:\GuardianD008\wheelhouse --require-hashes `
    -r <project>\requirements-hashed.lock
& C:\GuardianD008\venv-check\Scripts\python.exe -m pip check
cd <project>; & C:\GuardianD008\venv-check\Scripts\python.exe -m pytest -p no:cacheprovider
```

Expected: eight packages installed from local wheels, `pip check` clean, **361 passed**.

## 4. Residual notes (not blockers)

- The wheelhouse lives on this host, outside git; the repository keeps its manifest and hashed
  lock, so provenance is verifiable, but a fresh machine must re-run
  `scripts/build_wheelhouse.py` (network) or receive the wheelhouse out-of-band.
- `pip list` returns an empty array in this environment even though `importlib.metadata` sees all
  distributions (a pip quirk with the non-ASCII project path). Version proof therefore uses
  `importlib.metadata`, not `pip list`.
- `PIP_USER=1` is set globally; it must be unset for a venv install (`--user` is refused inside a
  venv). Documented in the commands above.

## 5. What is NOT claimed

- D-008 is **not** marked CLOSED; the independent Inspector must confirm it.
- No trading, MT5 order path, account field or safety boundary was touched.


## 6. Integration-branch qualification (2026-11-22)

This report preserves the engineering claims and reproduction instructions from the source D-008 candidate. The integration branch is a different snapshot: later Phase 4/5/11 records were retained, the dependency lock was carried forward, and `build_wheelhouse.py` was hardened to refuse a non-empty output directory and verify the exact eight-package/version closure before writing manifests. Consequently, the source evidence file's embedded file hashes describe the original candidate snapshot, not every file byte on this integration branch. The evidence sidecar in this branch hashes the committed evidence text itself. No test suite or independent Inspector run has been executed against this integration snapshot in this session; it remains **CANDIDATE / NOT ACCEPTED** until those checks are rerun.

## Integration snapshot (2026-11-22, branch `integration/d008-offline-closure-20261122`)

Reproduction on the integration HEAD found a real defect: `requirements-hashed.lock` carried a
malformed `pytest` digest (not 64 hex characters) and a `packaging` digest that did not match
the wheel, so `pip install --require-hashes` could not succeed. The lock was regenerated from
`WHEELHOUSE.sha256` (single source of truth) and `scripts/build_wheelhouse.py` gained a
`--verify` mode that compares lock, manifest and actual wheel bytes, reporting missing, extra,
stale, version-mismatched and closure-mismatched wheels. Negative paths are covered by
`tests/unit/test_d008_wheelhouse.py` (8 tests, no network).

Fresh hermetic venv `C:\GuardianD008\venv-integration` (Python 3.11.8,
`include-system-site-packages=false`): offline install with `--no-index --require-hashes`
succeeded, `pip check` clean, **372 passed**, `compileall` exit 0, `--verify` OK.
No independent PASS is claimed for this HEAD.
