# Agentic Migration Validator

Agentic Migration Validator is a local, credentials-free workflow for checking whether a PostgreSQL migration is safe to promote.

It compares source and target databases, produces structured findings, enforces deterministic readiness gates, persists audit-ready workflow state, and drafts runbook guidance that must stay tied to evidence.

The core design principle is:

> Advisors propose. Deterministic invariants dispose.

Model-backed advisors may explain, summarize, and draft runbook guidance. They do not decide whether a migration is safe. Database inspection, checksum validation, schema checks, evidence validation, risk scoring, approvals, and safety gates remain deterministic.

## Why This Exists

A migration validation system should not ask an LLM, "Is this safe to cut over?"

The safer pattern is:

1. Deterministic tools inspect the source and target databases.
2. The tools emit structured findings with evidence references.
3. Gatekeeper logic decides whether cutover or readiness is allowed.
4. Advisors explain the decision only when their claims are supported by findings and gate results.
5. Human approvals are recorded as auditable inputs, not as manual overrides of readiness.

The fixture suite includes a concrete example of why this matters:

- `missing_rows` and `replication_lag` both have the same missing target payment row.
- `missing_rows` blocks readiness because the row loss is unexplained.
- `replication_lag` stays non-blocking because a declared source freshness cutoff explains the gap.

Same symptom, different verdict. The model may narrate the result, but the deterministic gate owns the decision.

## What It Demonstrates

- PostgreSQL source/target fixture validation with deterministic checksum and schema checks.
- Policy-aware validation where the same row gap can either block readiness or remain an explained lag condition.
- Structured findings across `migration_integrity`, `compatibility_advisory`, and `process_control` risk axes.
- Gatekeeper decisions that enforce cutover/readiness instead of asking an advisor to decide safety.
- Evidence-bound runbook drafts whose claims must trace back to deterministic findings and gate results.
- A local dashboard that launches workflow runs, persists audit-ready state, records approvals, and resolves artifact/evidence details.

## Who It Is For

This project models the control layer around a database migration. It is not a one-click migration tool, a hosted production service, or a live cutover runner.

It is useful for:

| Use Case | What The System Does | Why It Matters |
| --- | --- | --- |
| Pre-cutover validation rehearsal | Compares PostgreSQL source and target fixtures, emits structured findings, and blocks readiness when data integrity fails. | A migration team can see whether the target is safe to promote before a cutover window. |
| Post-migration data integrity check | Runs canonical row/table checksums and schema-triggered data checks after a migration run. | Row counts can match while values drift; canonical checks catch content differences that simple counts miss. |
| Schema drift triage | Separates catalog differences from row-data impact, including cases where relaxed constraints are harmless versus integrity-breaking. | Teams can distinguish advisory schema differences from differences that should block readiness. |
| Evidence-bound runbook drafting | Produces runbook sections and recommendations from deterministic findings and gate results, then validates that claims stay evidence-bound. | Advisors can summarize and explain, but they cannot invent readiness or talk past blocked gates. |
| Audit-ready approval workflow | Records human approvals as auditable inputs while gate outputs remain recomputed derived state. | Humans can approve validation evidence, but they cannot manually flip the system into ready. |
| Detector and gate regression suite | Runs seeded scenarios against expected findings, mismatch categories, and gate outcomes. | The project proves that detectors catch intended failures and that the eval runner catches misses, false positives, and mismatches. |

## Quickstart

Requirements:

- Python 3.11+
- Docker with Compose support
- `make`

Install test dependencies if needed:

```sh
python3 -m pip install -e ".[dev]"
```

Run the test suite:

```sh
make test
```

Start the fixture databases:

```sh
make db-up
```

Start the local API and dashboard:

```sh
make run-api
```

Open the dashboard:

```text
http://127.0.0.1:8080/
```

Stop the fixture databases when finished:

```sh
make db-down
```

Generated `artifacts/` and `runs/` directories are ignored by git because they are reproducible local outputs.

## Screenshot

![Agentic Migration Validator dashboard overview](docs/assets/dashboard-overview.png)

## Walkthrough

Start with the fastest contrast in the system: two runs that share the same missing target row.

1. In `New Run`, select `Missing Rows`, then run the workflow.
2. Open `Readiness Gates` and verify readiness is blocked by `validation.missing_rows`.
3. Run `Replication Lag`, which uses the same missing target payment row.
4. Verify the lag scenario stays non-blocking because the source freshness cutoff explains the gap.
5. Open `Run Artifacts`, choose the runbook draft, and inspect its evidence references.
6. Submit a validation approval in `Approval Action`.
7. Confirm `Approval State` and `Audit Trail` update while gate decisions remain derived state.

That contrast is the shortest way to understand the architecture: same data symptom, different verdict, because deterministic evidence and policy decide. The advisor explains the result; it does not decide safety.

For the schema-risk contrast, run or inspect:

- `Schema Drift`: a dropped uniqueness guarantee remains a low structural note when row data still satisfies uniqueness.
- `Relaxed Unique Violation`: the same dropped uniqueness guarantee becomes a blocking finding when target rows contain duplicates.
- `Broken Foreign Key`: dropped referential integrity becomes blocking when target rows contain orphaned references.

These scenarios show the same pattern from another angle: metadata identifies where a verdict is needed, row data determines whether migration integrity is actually broken, and gates own the safety decision.

## Scenario Guide

| Scenario | What Changed | What It Proves | Cutover/Ready |
| --- | --- | --- | --- |
| `clean_migration` | Source and target match. | A clean rehearsal emits no detector findings. | Allowed |
| `failed_checksum` | Row counts and schema match, but customer data changed. | Canonical checksums catch content drift that simple counts miss. | Blocked |
| `missing_rows` | A target payment row is missing with no lag policy explaining the gap. | Unexplained missing rows are migration-integrity failures. | Blocked |
| `replication_lag` | The same target row gap is covered by a known source freshness cutoff. | Explained lag is surfaced as non-blocking freshness context instead of row loss. | Allowed |
| `schema_drift` | A target schema guarantee is relaxed, but rows still satisfy the original guarantee. | Schema differences can be structural or advisory without corrupting migrated data. | Allowed |
| `schema_relaxed_unique_violation` | The target drops a uniqueness guarantee and migrated rows now contain duplicates. | The same relaxed constraint becomes blocking when row data violates the original guarantee. | Blocked |
| `broken_fk` | A target drops a foreign key and now has an order pointing at a missing customer. | Catalog drift can trigger a row-data check, and orphaned references become blocking. | Blocked |

Read each scenario through four outputs:

- `validation_findings`: row/data validation findings, such as checksum mismatches, missing rows, or explained replication lag.
- `schema_findings`: catalog-level findings, such as widened types, relaxed constraints, or extra target columns.
- `schema_data_check_results`: row-data checks triggered by schema relaxation, such as duplicate checks after a unique constraint is dropped or orphan checks after a foreign key is dropped.
- `gate_results`: deterministic `can_recommend_cutover` and `can_mark_ready` decisions, including the specific blocking finding keys.

## Core Concepts

| Concept | Meaning |
| --- | --- |
| Finding | A structured record with a stable `finding_key`, severity, scope, evidence references, and risk axis. |
| Evidence reference | A pointer to the deterministic data or artifact that supports a finding or runbook claim. |
| Gate | A deterministic readiness decision derived from findings, approvals, and policy. |
| Advisor | A runbook-drafting component that can explain gate decisions but cannot override them. |
| Approval | A human-reviewed input that is persisted and audited, but does not directly edit gate outputs. |
| Artifact bundle | A reproducible local package of eval reports, runbook drafts, evidence registry data, and hashes. |

## Risk Axes

Risk is separated into three axes:

- `migration_integrity`: whether the PostgreSQL migration being validated is correct.
- `compatibility_advisory`: prospective warehouse compatibility concerns.
- `process_control`: approvals, rollback criteria, evidence references, and governance.

PostgreSQL cutover readiness reads only `migration_integrity` and `process_control`. Compatibility advisory findings are reported separately and cannot block PostgreSQL cutover readiness.

## How It Works

The local workflow is intentionally simple:

1. Docker Compose starts source and target PostgreSQL fixture databases.
2. A scenario reset script loads the selected source/target state.
3. Deterministic detectors inspect row contents, schema metadata, row presence, freshness policy, uniqueness, nullability, and referential integrity.
4. Findings and evidence references are evaluated against expected outcomes.
5. Gatekeeper logic computes readiness and cutover decisions.
6. The workflow persists run state, audit events, artifact snapshots, approvals, and runbook drafts for the dashboard/API.

The dashboard and API are local-only by default. The API binds to localhost and is designed for local project evaluation, not internet exposure.

## Development Commands

Run tests:

```sh
make test
```

Equivalent direct command:

```sh
python3 -m pytest -q
```

Start or stop the fixture databases:

```sh
make db-up
make db-down
```

Load scenarios:

```sh
make db-reset
make db-reset SCENARIO=failed_checksum
```

Run one validation scenario:

```sh
make validate-scenario SCENARIO=failed_checksum
```

Run raw schema diff introspection:

```sh
make schema-diff SCENARIO=schema_drift
```

Run all deterministic fixture evals:

```sh
make eval-scenarios
```

Write a local artifact bundle:

```sh
make write-artifacts
```

Run the local fixture workflow:

```sh
make run-workflow
```

Serve the local API and dashboard:

```sh
make run-api
```

Smoke-test the running local API:

```sh
make api-smoke
SMOKE_WORKFLOW_SCENARIO=failed_checksum make api-smoke
```

Exercise one gate as a hard stop:

```sh
make enforce-gate SCENARIO=failed_checksum GATE=can_mark_ready
```

That command exits nonzero when the selected gate is blocked. The same command with `SCENARIO=clean_migration` exits successfully.

Generate a deterministic runbook draft:

```sh
make draft-runbook SCENARIO=failed_checksum
```

Enable optional live model prose:

```sh
RUNBOOK_MODEL_CALLS=enabled OPENAI_API_KEY=... OPENAI_MODEL=... make draft-runbook SCENARIO=failed_checksum
```

The default local workflow is credentials-free. Live model generation is optional and still passes through boundary validation. If generated prose makes unsupported causal claims, boundary validation fails and the command exits nonzero.

## Local API

The same server renders the dashboard at `http://127.0.0.1:8080/` and exposes JSON routes for workflow state, artifacts, evidence, readiness, approvals, audit events, and retries.

Implemented routes:

- `GET /`
- `GET /ui/{asset}`
- `GET /health`
- `GET /scenarios`
- `GET /artifacts/latest-manifest`
- `GET /artifacts/{artifact_id}`
- `GET /evidence/{evidence_ref}`
- `GET /workflows`
- `GET /workflows/latest`
- `GET /workflows/{workflow_run_id}`
- `GET /workflows/{workflow_run_id}/artifacts/{artifact_id}`
- `GET /workflows/{workflow_run_id}/evidence/{evidence_ref}`
- `GET /workflows/{workflow_run_id}/audit`
- `GET /workflows/{workflow_run_id}/approvals`
- `GET /workflows/{workflow_run_id}/readiness`
- `POST /workflows/{workflow_run_id}/approvals`
- `POST /workflows/{workflow_run_id}/retry`
- `POST /workflows/run`

The dashboard launches fixture workflows, shows readiness, approvals, blocking findings, and next actions first, then keeps artifact/evidence, audit, and run diagnostics behind optional disclosure sections. Approval controls submit auditable records through the API; failed runs can be retried as new runs; gate outputs remain derived state.

## Implemented Capabilities

| Area | Implemented In |
| --- | --- |
| Axis-aware risk scoring | `tools/risk_scoring.py` |
| Canonical row and table checksums | `tools/checksum.py`, `tools/checksum_validation.py` |
| Row-presence and lag-aware freshness checks | `tools/row_validation.py` |
| Schema introspection and schema diffing | `tools/schema_introspection.py`, `tools/schema_diff.py` |
| Schema delta policy mapping | `tools/schema_policy.py` |
| Schema-triggered row-data checks | `tools/schema_policy.py`, `tools/schema_diff.py` |
| Eval matching | `tools/eval_runner.py` |
| Deterministic gates | `tools/gatekeeper.py`, `tools/readiness.py` |
| Evidence-bound runbook drafts | `tools/runbook_advisor.py`, `tools/live_model.py` |
| Artifact bundles and evidence registry | `tools/artifacts.py` |
| Local workflow orchestration | `tools/workflow.py` |
| Audit event validation | `tools/audit.py` |
| Run persistence and artifact snapshots | `tools/run_store.py` |
| Human approvals | `tools/approvals.py` |
| Stage transition checks | `tools/transitions.py` |
| Local JSON API | `tools/api.py` |
| Local dashboard | `ui/` |
| Fixture databases and seeded scenarios | `docker-compose.yml`, `fixtures/` |

## Project Structure

```text
docs/
  Architecture, API, artifact, audit, evidence, gatekeeper, fixture, and runbook contracts.

fixtures/
  Base PostgreSQL schema/data plus seeded source/target scenario states.

scripts/
  CLI entry points for validation, evals, schema diffing, artifacts, workflow runs, and the API server.

tests/
  Unit, integration, workflow, API, static UI, schema, gatekeeper, approval, audit, and eval tests.

tools/
  Deterministic validation, policy, gatekeeper, advisor, artifact, persistence, and API modules.

ui/
  Dependency-free local dashboard.

Makefile
docker-compose.yml
pyproject.toml
```

## Documentation

The repository includes implementation contracts for the pieces that matter most:

- `docs/architecture.md`
- `docs/api-contract.md`
- `docs/artifact-schemas.md`
- `docs/audit-events.md`
- `docs/evidence-references.md`
- `docs/fixture-plan.md`
- `docs/gatekeeper-invariants.md`
- `docs/product-requirements.md`
- `docs/runbook-advisor-boundary.md`
- `docs/security-audit.md`
- `docs/structured-finding-schema.md`
- `docs/demo-script.md`

## Current State

The deterministic validation spine is implemented and tested. The project includes checksum validation, row-presence checks, lag-aware freshness handling, schema introspection, schema-triggered data checks, enforced gatekeeper decisions, evidence-bound runbook drafts, local artifact bundles, persisted workflow/audit state, approval records, retry behavior for failed runs, and a local dashboard/API.

The currently implemented scenario set covers:

- Clean migration.
- Content drift with matching row counts.
- Missing rows versus explained replication lag.
- Schema drift without row-data impact.
- Relaxed uniqueness with duplicate target data.
- Dropped foreign key with orphaned target rows.

## Future Extensions

Future work should preserve the deterministic boundary:

- Add detector scenarios only when they prove a clear validation distinction the current scenarios do not already show.
- Add optional async workflow progress streaming only if the local API starts limiting workflow visibility.
- Add framework adapters only if a concrete deployment need appears; the current stdlib API is intentionally zero-dependency.
- Keep gate outputs derived from state, never edited directly.

MCP is intentionally deferred. The current implementation uses direct Python tool calls through typed internal functions so the same capabilities can later be exposed through MCP without changing detector logic.
