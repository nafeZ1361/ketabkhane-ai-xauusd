# Evidence Index

Use this index to find the source of each important claim. Keep evidence paths current.

## Label definitions
- **Verified remotely:** inspected directly in the referenced GitHub repository/ref.
- **User-reported:** the user provided a command result or stated a fact; not independently verified by the assistant.
- **Static review:** source inspected but not executed.
- **Unknown:** evidence is missing.

## Evidence

| Claim | Label | Evidence |
|---|---|---|
| New repository is public and `main` began at `de4e4507ab12acb0db79bb88e649f7c3662de80a` | Verified remotely | `STAGE_0_AUDIT.md` |
| Old source ref inspected is `36df7c9665ded188ab565d1fd4f25da63197c0f3` | Verified remotely | `STAGE_0_AUDIT.md`, `REUSE_DECISION.md` |
| Old backtest source has risks documented in the audit | Static review | `STAGE_0_AUDIT.md`, `REUSE_DECISION.md`; no runtime tests |
| Local CSV size 214,692,947 bytes | User-reported | PowerShell output in conversation; summarized in `AI_MEMORY/01_CURRENT_STATE.md` |
| Local CSV SHA-256 `E539F77788859C25F6D8B53606F89E7E3531AF1C46FF53207D9F0831DC2ACB9E` | User-reported | PowerShell `Get-FileHash` output; summarized in current state |
| Local CSV has 3,489,360 lines including header | User-reported, repeated | Two PowerShell full-file line counts matched; the simpler pass took 15.733 seconds. This does not validate row contents. |
| CSV source is user's Windows + MT5 + AMarkets | User-reported | User statement; server/timezone/export details remain unknown |
| Full-file integrity scan passed | Unknown / not claimed | User has not provided the scan output yet |
| CSV timestamps are UTC | Unknown | Must not assume |
| Data redistribution rights are established | Unknown | Must not assume |

## Evidence discipline
Every new test/evidence entry should include the exact command or test name, date, exit status, and concise output summary. Store no secrets, passwords, account numbers, or broker credentials.
