# Agentic Migration Validator

Agentic Migration Validator is a local workflow for assessing database migration readiness, validating post-migration integrity, and producing human-reviewed migration runbooks.

The core product idea is simple: advisors propose, deterministic invariants dispose. Model-backed advisors may synthesize plans, explanations, critiques, and runbooks, but database inspection, validation checks, risk scoring, evidence validation, and safety gates are deterministic.

## Current Status

This repo is in early Day 2 work. The product requirements and architecture contracts are drafted, deterministic risk scoring is implemented, checksum canonicalization is implemented, and the first PostgreSQL fixture environment is available.

Implemented today:

- Axis-aware risk scoring in `tools/risk_scoring.py`
- Canonical row and table checksums in `tools/checksum.py`
- Risk scoring test vectors in `docs/risk-scoring-test-vectors.md`
- Unit tests in `tests/`
- Foundation specs for architecture, findings, evidence references, gatekeeper invariants, fixtures, artifacts, audit events, and the initial API
- Docker Compose fixture databases for `source-postgres` and `target-postgres`
- Seed fixtures for `clean_migration` and `failed_checksum`

Not implemented yet:

- Database introspection
- Schema diffing
- Data validation detector tooling
- Workflow orchestration
- FastAPI backend
- Vite React dashboard
- Evaluation runner
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
  test_risk_scoring.py
tools/
  checksum.py
  risk_scoring.py
fixtures/
  base/
  scenarios/
scripts/
  reset_databases.sh
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

Stop the fixture databases:

```sh
make db-down
```

## Next Milestone

Day 2 should continue the deterministic database foundation:

- Implement initial database introspection
- Begin row count and schema comparison detectors
- Add eval comparison against expected-findings fixtures

## Design Boundary

MCP is intentionally deferred to phase two. The MVP should use direct Python tool calls through typed internal functions so the same capabilities can later be exposed through MCP without changing detector logic.
