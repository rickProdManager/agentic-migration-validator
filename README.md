# Agentic Migration Validator

Agentic Migration Validator is a local workflow for assessing database migration readiness, validating post-migration integrity, and producing human-reviewed migration runbooks.

The core product idea is simple: advisors propose, deterministic invariants dispose. Model-backed advisors may synthesize plans, explanations, critiques, and runbooks, but database inspection, validation checks, risk scoring, evidence validation, and safety gates are deterministic.

## Current Status

The deterministic validation spine is implemented. The product requirements and architecture contracts are drafted, risk scoring is available, checksum validation runs against Docker PostgreSQL fixtures, eval matching is calibrated, schema introspection emits structured findings, gatekeeper checks enforce cutover/readiness state, and runbook drafts remain evidence-bound.

Implemented capabilities:

- Axis-aware risk scoring in `tools/risk_scoring.py`
- Canonical row and table checksums in `tools/checksum.py`
- Checksum validation findings in `tools/checksum_validation.py`
- Detection eval matching in `tools/eval_runner.py`
- Raw schema introspection and diffing in `tools/schema_introspection.py` and `tools/schema_diff.py`
- Axis-first schema delta policy mapping in `tools/schema_policy.py`
- Schema-triggered data checks for relaxed nullability and dropped unique constraints
- Deterministic cutover/readiness gate checks in `tools/gatekeeper.py`
- Evidence-bound runbook draft generation in `tools/runbook_advisor.py`
- Optional live model prose for runbook drafts in `tools/live_model.py`
- Reproducible local artifact bundles in `artifacts/`
- Artifact metadata, hashing, and validation in `tools/artifacts.py`
- Evidence registry generation and reference resolution for artifact bundles
- Dependency-free local JSON API surface in `tools/api.py`
- Local workflow run response in `tools/workflow.py`
- Risk scoring test vectors in `docs/risk-scoring-test-vectors.md`
- Unit tests in `tests/`
- Foundation specs for architecture, findings, evidence references, gatekeeper invariants, fixtures, artifacts, audit events, and the initial API
- Docker Compose fixture databases for `source-postgres` and `target-postgres`
- Seed fixtures for `clean_migration`, `failed_checksum`, `schema_drift`, and `schema_relaxed_unique_violation`

Not implemented yet:

- Additional data validation detectors beyond checksum
- Full workflow orchestration
- Full FastAPI backend
- Vite React dashboard

## MVP Scope

The MVP validates a real PostgreSQL-to-PostgreSQL migration while also reporting separate advisory risks against a Snowflake-like target profile.

Risk is separated into three axes:

- `migration_integrity`: whether the PostgreSQL migration being validated is correct
- `compatibility_advisory`: prospective warehouse compatibility concerns
- `process_control`: approvals, rollback criteria, evidence references, and governance

PostgreSQL cutover readiness reads only `migration_integrity` and `process_control`. Compatibility advisory findings are reported separately and cannot block PostgreSQL cutover readiness.

## Repository Map

```text
docs/
  api-contract.md
  architecture.md
  artifact-schemas.md
  audit-events.md
  evidence-references.md
  fixture-plan.md
  gatekeeper-invariants.md
  product-requirements.md
  risk-scoring-test-vectors.md
  runbook-advisor-boundary.md
  structured-finding-schema.md
tests/
  test_api.py
  test_artifacts.py
  test_checksum.py
  test_checksum_validation.py
  test_eval_runner.py
  test_fixtures.py
  test_gatekeeper.py
  test_risk_scoring.py
  test_runbook_advisor.py
  test_schema_diff.py
  test_schema_introspection.py
  test_schema_policy.py
  test_workflow.py
tools/
  api.py
  artifacts.py
  checksum.py
  checksum_validation.py
  eval_runner.py
  gatekeeper.py
  risk_scoring.py
  runbook_advisor.py
  schema_diff.py
  schema_introspection.py
  schema_policy.py
  workflow.py
fixtures/
  base/
  scenarios/
scripts/
  diff_schema.py
  generate_runbook.py
  run_eval.py
  serve_api.py
  run_workflow.py
  write_artifacts.py
  reset_databases.sh
  validate_scenario.py
docker-compose.yml
Makefile
pyproject.toml
```

## Foundation Docs

| Deliverable | Status |
| --- | --- |
| README draft | Done |
| Architecture doc | Done |
| Fixture plan | Done |
| Initial API contract | Done |
| Gatekeeper invariant spec | Done |
| Evidence-reference spec | Done |
| Structured finding schema with `record_type`, `risk_axis`, and `finding_key` | Done |
| Artifact schemas | Done |
| Audit event schema | Done |

## Development

Use the project-local test command:

```sh
make test
```

Equivalent direct command:

```sh
python3 -m pytest -q
```

Start the fixture databases:

```sh
make db-up
```

Load the clean scenario:

```sh
make db-reset
```

Load the failed-checksum scenario:

```sh
make db-reset SCENARIO=failed_checksum
```

Run checksum validation for a scenario:

```sh
make validate-scenario SCENARIO=failed_checksum
```

Run raw schema diff introspection for a scenario:

```sh
make schema-diff SCENARIO=schema_drift
```

Run deterministic fixture evals:

```sh
make eval-scenarios
```

The eval report includes `can_recommend_cutover` and `can_mark_ready` gate results for each fixture scenario.

Write a local artifact bundle:

```sh
make write-artifacts
```

This writes a validated eval report and runbook drafts under `artifacts/`. The generated directory is ignored by git because artifacts are reproducible local outputs.
The bundle includes an evidence registry so artifact evidence refs resolve to stored bundle entries.

Run the local fixture workflow:

```sh
make run-workflow
```

This emits an API-shaped workflow response with step status, scenario IDs, artifact refs, workflow validation, and the artifact manifest. It is the local contract the future backend can wrap.

Serve the local JSON API:

```sh
make run-api
```

Implemented routes:

- `GET /health`
- `GET /scenarios`
- `GET /artifacts/latest-manifest`
- `GET /artifacts/{artifact_id}`
- `GET /evidence/{evidence_ref}`
- `POST /workflows/run`

Smoke-test the running local API:

```sh
make api-smoke
```

With Docker fixtures running, smoke-test the workflow and retrieval routes:

```sh
SMOKE_WORKFLOW_SCENARIO=failed_checksum make api-smoke
```

Enforce one gate for one scenario:

```sh
make enforce-gate SCENARIO=clean_migration GATE=can_mark_ready
```

This command exits nonzero when the gate is blocked.

Generate a deterministic runbook draft for one scenario:

```sh
make draft-runbook SCENARIO=failed_checksum
```

Live model prose is opt-in and still passes through boundary validation:

```sh
RUNBOOK_MODEL_CALLS=enabled OPENAI_API_KEY=... OPENAI_MODEL=... make draft-runbook SCENARIO=failed_checksum
```

The default portfolio demo is credentials-free; live generation has not been executed in this repository because no API key is required for the deterministic safety checks. The boundary is validated deterministically against adversarial prose, so the safety property does not depend on model behavior.

The live path uses deterministic gate results as the source of truth. If generated prose makes unsupported causal claims, boundary validation fails and the command exits nonzero.

Stop the fixture databases:

```sh
make db-down
```

## Demo Walkthrough

Run the deterministic fixture suite:

```sh
make eval-scenarios
```

The command resets Docker-managed source and target PostgreSQL databases for each scenario, runs checksum validation, runs schema introspection and schema-triggered data checks, compares produced findings to expected findings, and evaluates cutover/readiness gates. Model calls are disabled.

The four implemented scenarios show the core pattern:

| Scenario | What It Proves | Cutover/Ready |
| --- | --- | --- |
| `clean_migration` | Source and target data/schema match. No detector findings are emitted. | Allowed |
| `failed_checksum` | Data content drift is caught by canonical checksums even when row counts match. | Blocked |
| `schema_drift` | Schema differences can be structural or advisory without corrupting migrated data. Relaxed guarantees trigger row-data checks, and clean row data stays non-blocking. | Allowed |
| `schema_relaxed_unique_violation` | The same relaxed unique constraint becomes a blocking integrity finding when target row data contains duplicates. | Blocked |

Read each scenario result through three fields:

- `validation_findings`: row/data validation findings, such as canonical checksum mismatches.
- `schema_findings`: catalog-level findings, such as widened types, relaxed constraints, or extra target columns.
- `schema_data_check_results`: row-data checks triggered by schema relaxation, such as duplicate checks after a unique constraint is dropped.
- `gate_results`: deterministic `can_recommend_cutover` and `can_mark_ready` decisions, including the specific blocking finding keys.

The important distinction is visible in the two schema scenarios. `schema_drift` drops a unique constraint but keeps payment references unique, so it emits a low structural finding and the duplicate check passes. `schema_relaxed_unique_violation` drops the same constraint and introduces duplicate payment references, so the triggered data check emits a high blocking validation finding.

That is the central design boundary: detectors and data checks produce structured facts; the gatekeeper decides whether those facts block cutover/readiness; future advisors may explain or summarize, but they do not decide safety.

To exercise the gatekeeper as a hard stop, run:

```sh
make enforce-gate SCENARIO=failed_checksum GATE=can_mark_ready
```

That command exits nonzero because the checksum mismatch blocks readiness. The same command with `SCENARIO=clean_migration` exits successfully.

## Next Milestone

The next milestone should wrap the validated artifact layer:

- Expand the local API only where the workflow needs it
- Run adversarial live-model reviews for `failed_checksum` and `schema_relaxed_unique_violation`

## Design Boundary

MCP is intentionally deferred to phase two. The MVP should use direct Python tool calls through typed internal functions so the same capabilities can later be exposed through MCP without changing detector logic.
