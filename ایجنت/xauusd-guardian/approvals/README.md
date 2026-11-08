# Approvals

Structured approval records. Written by `scripts/record_approval.py`, one JSON file per approval, chained by `prev_sha256`.

## What a record proves

- The record body has not been edited since it was written (`record_sha256`).
- The chain is unbroken from `GENESIS` to the newest record (`prev_sha256`).

## What it does NOT prove

A local hash chain is **not** a cryptographic human signature and does not authenticate the approver's identity. Treat it as tamper evidence only.

## Rules

- Never infer an approval from silence, from an unrelated earlier approval, or from an agent's own statement.
- An expired record is not an approval.
- Approvals are append-only: never rewrite `A-*.json`; issue a new ID instead.

## Current records

| ID | Action | Phase | Status |
|---|---|---|---|
| A-01 | create project workspace | 1 | GRANTED |
| A-02 | venv + pinned dependencies | 1 | GRANTED |
| A-03 | local git repository | 1 | GRANTED |
| A-04 | read balance/equity | 4 | NOT REQUESTED |
| A-05 | DEMO order checks / execution | 5 / 11 | NOT REQUESTED |
