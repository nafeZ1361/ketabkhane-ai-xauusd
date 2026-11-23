# D-008 — Offline dependency closure (2026-11-22)

Status: **ACCEPTED WITH NON-BLOCKING FOLLOW-UP** — independent inspection PASS is recorded for the D-008 integration snapshot and PR #8 local verification. D-1 is applied and independently verified. The owner accepted D-2 as a non-blocking follow-up; ACLs remain unchanged. Phase 5 entry gates are separately controlled.

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


## 7. Independent integration inspection and administrative disposition (2026-11-23)

### Frozen snapshot and verdict

- Inspected branch: `integration/d008-offline-closure-20261122`
- Inspected HEAD: `cc106b557586e3e4cd867897c642ae7dc7d3fd16`
- Independent Inspector verdict: **PASS**
- External Inspector report: `C:\GuardianInspect\reports\d008-final-inspection-20261122T1955Z.md`
- External Inspector report SHA-256: `029d9e9546514b4c058786c950abb542ef117a1361ae8fbe4f5318714b17079c`
- Both mirrored agent-log files are byte-identical; each SHA-256 is `3ead974ca6109d9754e3c3fe3195f801fb60950036c475d0fc3534abdc2c474a`.
- Frozen snapshot manifest: 140 files; SHA-256 `912dbd85…0626`; independently reproduced from the exact commit with zero differences.
- Independent suite: **374 passed / 0 failed / 0 errors**; `compileall` exit 0; snapshot unchanged during inspection.
- Primary evidence SHA-256: `97d43f1b…1cec`
- JUnit SHA-256: `7f6ccb45…d6c6`
- Builder verification SHA-256: `6af40108…e3f0`
- Offline installation SHA-256: `1517a57a…529a`

### Findings

- **D-1 — APPLIED / INDEPENDENTLY VERIFIED.** In the PR #8 verification worktree, the Windows ReadOnly bit was applied to the exact `WHEELHOUSE.sha256` and `requirements-hashed.lock` files. Hashes remained unchanged; write-open was denied. This is an operational attribute, not ACL protection.
- **D-2 — OWNER ACCEPTED AS NON-BLOCKING FOLLOW-UP (2026-11-23).** The owner explicitly accepts this residual as non-blocking. Existing ACLs must remain unchanged. All future snapshots must be created beneath an Owner-only root/path with restrictive inheritance, followed by independent effective-access verification. No claim is made that current ACL exposure has been remediated.
- **D-3 — VERIFIED / UNUSED / PRESERVED.** External file `C:\GuardianD008\requirements-hashed.lock` SHA-256: `404f36ed4512d1ac97c4b5d4a64f3bff152b07a3e3754224e734c28670126b8c`. It mismatches the committed lock SHA-256 `ed42dbdc2c65bb1393c1313e9ffdc897badb615d41e41e337ab8109db1b81970`. The external file was not changed or deleted.
- **D-4 — DISCLOSED / EVIDENCE SUPPLIED.** The Inspector independently recorded the final suite count and builder verification. The earlier Developer-evidence omission remains disclosed; historical evidence was not rewritten.

### Scope and closure rule

No trading behavior, source code, dependencies, wheel files, wheel contents, ACLs, or PR #7 were changed by the Inspector or by the reported local administrative inspection. No branch switch, commit, push, merge, deletion or cleanup was performed by that inspection.

D-008 is **ACCEPTED WITH A DISCLOSED NON-BLOCKING D-2 FOLLOW-UP**. The owner disposition is recorded; D-1 is independently verified. The PR #8 local verification report for exact head c3b5ca9efe2d8fea9168a712c47d1482f814769e has SHA-256 60cd8d923ae7341a56c7f96526240672f557347d0ed6750b08bfdd25a697b29b and records 377/0/0, compileall, hermetic offline install, clean pip check, wheel verification and 19/19 content checks. No ACL was changed. The residual requires Owner-only roots for future snapshots and remains disclosed; it is not a claim of ACL remediation. Phase 5 entry gates remain separate and must still be formally closed.


## 7. Owner disposition and PR #8 local verification (2026-11-23)

- **D-2 owner decision:** accepted as a **non-blocking follow-up**. Existing ACLs remain unchanged; no ACL change is authorized or claimed.
- **Future snapshots:** must be created under an Owner-only root/path with restrictive inheritance, then independently checked for effective access.
- **D-1:** the exact WHEELHOUSE.sha256 and requirements-hashed.lock files received the Windows ReadOnly attribute in the PR #8 verification worktree. Their hashes were unchanged, write-open was denied, and the independent Inspector verified the preserved copy. This is not ACL protection.
- **PR #8 exact head:** c3b5ca9efe2d8fea9168a712c47d1482f814769e.
- **Local verification report:** pr8-verification-report-20261123T1550Z.md; SHA-256 60cd8d923ae7341a56c7f96526240672f557347d0ed6750b08bfdd25a697b29b. The report records 377/0/0 tests, compileall, hermetic offline install, clean pip check, wheel verification and 19/19 content checks.
- **Administrative disposition:** D-008 is accepted with the D-2 residual disclosed as non-blocking. D-3 remains unused/preserved and D-4 remains disclosed. Phase 5 formal entry gates remain separate; this addendum does not authorize trading, merge PR #8, or change ACLs.

## AP-7 independent PASS and Phase 5 entry status (2026-11-23)

- Exact inspected HEAD: `177cf62d2cce6b69fd7ecbe92d2bfde9a789c59d`; tree `ec607842883e25832e08478210ff55fa69e24166`; Inspector `DESKTOP-2NLF7CP\GuardianInspector`, SID `...-1004`, logon ID `S-1-5-5-0-1350151026`, session 25, Medium; snapshot 243 files; manifest `34ac2f22...da9f` before=after.
- Tests: **377/0/0**; hermetic offline install 8/8; `pip check` clean; `builder --verify` OK; `compileall` exit 0.
- Report `artifacts/ap7-inspector-run-20261123T175859Z/INSPECTION-REPORT.md` SHA-256 `47a9e1f6...0f0d`; Inspector evidence `18ab43b2...443c`; JUnit `793cf5c8...2b21`.
- D-4 remains **OPEN/ADVISORY** and non-blocking; D-2 remains owner-accepted; D-3 preserved/unused. No ACL/code change.
- Phase 5 entry remains **BLOCKED** on current preflight evidence; F1-F8 NOT STARTED.