# Agentic Migration Validator

Agentic Migration Validator is a local workflow for assessing database migration readiness, validating post-migration integrity, and producing human-reviewed migration runbooks.

The core product idea is simple: advisors propose, deterministic invariants dispose. Model-backed advisors may synthesize plans, explanations, critiques, and runbooks, but database inspection, validation checks, risk scoring, evidence validation, and safety gates are deterministic.

## Current Status

This repo is in Day 2 deterministic validation work. The product requirements and architecture contracts are drafted, risk scoring is implemented, checksum validation runs against Docker PostgreSQL fixtures, eval matching is calibrated, and schema introspection now emits structured findings.

Implemented today:

- Axis-aware risk scoring in `tools/risk_scoring.py`
- Canonical row and table checksums in `tools/checksum.py`
- Checksum validation findings in `tools/checksum_validation.py`
- Detection eval matching in `tools/eval_runner.py`
- Raw schema introspection and diffing in `tools/schema_introspection.py` and `tools/schema_diff.py`
- Axis-first schema delta policy mapping in `tools/schema_policy.py`
- Schema-triggered data checks for relaxed nullability and dropped unique constraints
- Risk scoring test vectors in `docs/risk-scoring-test-vectors.md`
- Unit tests in `tests/`
- Foundation specs for architecture, findings, evidence references, gatekeeper invariants, fixtures, artifacts, audit events, and the initial API
- Docker Compose fixture databases for `source-postgres` and `target-postgres`
- Seed fixtures for `clean_migration`, `failed_checksum`, and `schema_drift`

Not implemented yet:

- Persisted eval report artifacts
- Additional conditional-escalation fixtures where relaxed schema guarantees are breached in row data
- Additional data validation detectors beyond checksum
- Workflow orchestration
- FastAPI backend
- Vite React dashboard
- Model-backed advisor calls

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
  structured-finding-schema.md
tests/
  test_checksum.py
  test_checksum_validation.py
  test_eval_runner.py
  test_fixtures.py
  test_risk_scoring.py
  test_schema_diff.py
  test_schema_introspection.py
  test_schema_policy.py
tools/
  checksum.py
  checksum_validation.py
  eval_runner.py
  risk_scoring.py
  schema_diff.py
  schema_introspection.py
  schema_policy.py
fixtures/
  base/
  scenarios/
scripts/
  diff_schema.py
  run_eval.py
  reset_databases.sh
  validate_scenario.py
docker-compose.yml
Makefile
pyproject.toml
```

## Day 1 Deliverables

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

Stop the fixture databases:

```sh
make db-down
```

## Next Milestone

Day 2 should continue the deterministic database foundation:

- Add a failing conditional-escalation scenario for relaxed nullability or dropped uniqueness
- Add row count and additional validation detectors

## Design Boundary

MCP is intentionally deferred to phase two. The MVP should use direct Python tool calls through typed internal functions so the same capabilities can later be exposed through MCP without changing detector logic.
