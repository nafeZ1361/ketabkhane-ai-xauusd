# Second Brain — proposed Schema v0.1 (DESIGN ONLY)

Status: PROPOSAL — NOT LOCKED; the companion machine-readable draft is schema-proposal-v0.1.json. Layer 1 implementation is prohibited until the owner sends the exact command: قفل Schema v0.1.

## 1. Purpose and safety boundary

A separate, auditable knowledge system that learns only from reviewed Guardian events. It stores evidence, hypotheses, decisions, failures, verified fixes and reusable procedures. It must not autonomously change Guardian rules, code, risk limits, strategies or execution permissions.

Initial Guardian connection is strictly read-only. No broker credentials, account identifiers, Equity/Balance, private user data, order payloads or secrets may enter this schema.

## 2. Core entities

| Entity | Required fields | Purpose |
|---|---|---|
| SourceArtifact | id, source_type, uri_or_repo_path, revision, sha256, captured_at_utc | Immutable provenance for code, logs, reports and docs. |
| Observation | id, source_artifact_id, observed_at_utc, component, symptom, raw_evidence_ref | Directly observed event, not interpretation. |
| Finding | id, observation_ids[], claim, severity, status, confidence, reviewer_id | Falsifiable defect or capability gap. |
| Hypothesis | id, finding_id, explanation, predictions[], status | Candidate causal explanation; never stored as fact. |
| Experiment | id, hypothesis_id, method, inputs_hash, environment, expected, actual, result | Reproducible test or probe. |
| Decision | id, finding_id, choice, rationale, owner_approval_ref, decided_at_utc | Human-approved disposition. |
| Remediation | id, finding_id, code_revision, changed_paths[], tests[], rollback_ref | Traceable fix and regression protection. |
| Verification | id, remediation_id, inspector_identity, independence_proof, snapshot_hash, verdict, evidence_refs[] | Independent acceptance evidence. |
| Lesson | id, source_finding_id, rule, applicability, contraindications, status | Candidate reusable lesson; promoted only after verification. |
| Skill | id, name, version, source_repo, source_commit, content_hash, permission_scope, status | Versioned procedural skill with provenance. |
| SkillRun | id, skill_id, task_ref, inputs_hash, outputs_hash, outcome, reviewer_verdict | Evidence of skill use and quality. |
| Link | id, from_type, from_id, relation, to_type, to_id | Typed graph edges among entities. |

All timestamps are timezone-aware UTC. IDs are opaque stable identifiers. All content records carry schema_version, created_at_utc, updated_at_utc and provenance.

## 3. Lifecycle and learning gates

1. Capture immutable references and hashes; never silently rewrite source evidence.
2. Extract Observations with exact file/line/test references.
3. Analyze by creating Findings and competing Hypotheses; distinguish fact from inference.
4. Test with recorded inputs, environment, commands, exit codes and outputs.
5. Decide only with explicit owner disposition for policy or scope changes.
6. Remediate with code revision, changed paths, tests and rollback.
7. Inspect a frozen snapshot with a separate read-only Inspector and independence proof.
8. Promote only verified lessons to ACTIVE; blocked, disputed or uninspected lessons remain CANDIDATE or REJECTED.
9. Reuse lessons by component, failure signature, version and applicability; require a regression test before using a lesson to change code.

## 4. Status enums

- Finding: OPEN | CONFIRMED | DISPUTED | FIXED | DEFERRED | REJECTED
- Hypothesis: PROPOSED | TESTING | SUPPORTED | REFUTED
- Experiment: PLANNED | RUNNING | PASS | FAIL | INVALID
- Verification: PENDING | PASS | BLOCK | INDEPENDENCE_NOT_ESTABLISHED
- Lesson: CANDIDATE | ACTIVE | SUPERSEDED | REJECTED
- Skill: DISCOVERED | REVIEWED | APPROVED | DEPRECATED

## 5. Integrity and security invariants

- Append-only evidence and decision history; corrections create new records referencing superseded records.
- SHA-256 every imported artifact; store exact revision and source URI/path.
- No automatic promotion from model-generated text or a single successful run.
- Never infer causality from correlation; store alternatives and falsification tests.
- Retrieval returns provenance and status, not only generated summaries.
- Separate read/write capabilities. Guardian connector begins read-only.
- Redact secrets and sensitive account/user data before ingestion.
- Skills have explicit allowlists, read/write scopes, timeouts, token budgets and approval gates.
- Rejected lessons cannot re-enter ACTIVE without new linked verification.
- Generated recommendations remain advisory until a human decision is recorded.

## 6. Initial storage recommendation

Use SQLite with append-only event tables and normalized entity tables; no vector database in v0.1. Begin with deterministic indexed retrieval over component, error code, file path, strategy version, status and text. Add embeddings only after measured retrieval failures justify RAM/dependency cost.

## 7. Acceptance tests required before Layer 1

- Hash mismatch rejects ingestion.
- Source revision and exact evidence reference are mandatory.
- A model-generated lesson cannot become ACTIVE without independent PASS and owner approval where policy changes.
- Read-only Guardian connector cannot write to Guardian or invoke broker/MT5 APIs.
- Secret/account-data redaction is tested with adversarial fixtures.
- Append-only update creates a superseding record; it does not mutate history.
- Retrieval returns supporting evidence and contraindications.
- Rejected/deferred lessons are excluded from active recommendations.
- Migrations are reversible or explicitly forward-only with tested backup/restore.

## 8. Open owner decisions

- Separate repository name and ownership.
- Retention policy and backup location.
- Whether private notes may be ingested (default: no).
- Whether approved lessons can be suggested automatically (default: suggestions only).
- Exact inspector identity and proof mechanism for the Second Brain repository.

No code, database, connector or background learner is created by this proposal.
