# Architecture

## MVP Shape

Agentic Migration Validator is a local workflow application for validating database migration readiness. The phase-one architecture keeps deterministic tooling in charge of facts, checks, scoring, and safety gates while reserving model-backed advisors for synthesis and review.

The architecture exists because migration safety is not a prose problem. For example, `missing_rows` and `replication_lag` share the same missing target row, but one blocks readiness and the other does not because a declared freshness cutoff changes the policy verdict. That decision belongs to deterministic evidence and gates; an advisor may explain it, but it cannot make or override it.

```text
Dependency-free local dashboard
        |
Dependency-free local JSON API
        |
Workflow orchestrator
        |
Deterministic stages and advisor adapters
        |
Typed Python tool layer
        |
PostgreSQL source and target
        |
JSON and Markdown artifacts
```

## Components

### Frontend

The frontend opens directly into a migration workspace. The current dashboard launches fixture workflows, shows persisted runs, scenarios, workflow state, result/progress/transition summaries, readiness gates, blocking findings, artifacts, approvals, audit events, runbook sections, evidence reference resolution, and selected audit-event details. Approval controls submit auditable records through the backend; gate outputs remain derived state. Future UI work can add richer visual polish and async progress streaming.

The UI does not own gate state. It renders gate outputs computed by the backend. Approval and future accepted-risk controls must submit auditable workflow inputs rather than editing gate outputs.

### Backend API

The local backend exposes scenario listing, workflow execution, workflow/run retrieval, artifact and evidence lookup, approval submission, readiness views, retries, and audit logs. API handlers are thin: they load workflow state, call orchestration services, persist artifacts, and return structured response models. A framework adapter is optional future work, not a current release requirement.

### Workflow Orchestrator

The orchestrator owns stage ordering and resumability. The preferred MVP direction is LangGraph, but the phase-one contracts are plain Python data models so orchestration can start with a simpler service if needed.

Workflow state is the source of truth for:

- workspace id
- scenario id
- selected source and target database handles
- stage status
- discovery artifacts
- compatibility findings
- validation results
- risk reports
- approvals
- generated artifacts
- audit events

Humans may edit workflow inputs and approvals. They cannot edit gate outputs directly; gates are recomputed from workflow state.

### Deterministic Stages

Deterministic stages perform database inspection, schema comparison, validation checks, compatibility rule matching, risk scoring, evidence validation, and gate evaluation.

Implemented deterministic tools:

- `schema_introspection.py`
- `schema_diff.py`
- `schema_policy.py`
- `checksum_validation.py`
- `checksum.py`
- `eval_runner.py`
- `gatekeeper.py`
- `artifacts.py`
- `audit.py`
- `approvals.py`
- `readiness.py`
- `transitions.py`
- `workflow.py`
- `run_store.py`
- `api.py`
- `risk_scoring.py`

Future deterministic targets should stay tied to explicit scenario value. Additional backend work should stabilize contracts, smoke coverage, and demo ergonomics before adding framework or streaming complexity.

### Model-Backed Advisors

Advisors consume structured evidence and produce plans, explanations, runbooks, and critiques. Advisor output is never allowed to bypass deterministic gates.

Planned advisors:

- Migration Planner Advisor
- Compatibility Explanation Advisor
- Runbook Advisor
- Reviewer Advisor

Advisor claims that affect gates or risk must carry evidence references. Artifacts with unresolved evidence references are rejected.

### Tool Layer

Tools are plain Python functions with typed inputs and outputs. Database tools must use read-only roles for both source and target databases. Model-backed advisors do not receive raw connection strings and do not mutate databases directly.

The tool layer should be stable enough to expose through MCP in phase two without changing detector logic.

## Data Flow

1. User selects a scenario and starts a workflow run.
2. Discovery inspects source and target databases.
3. Compatibility applies the Snowflake-like target profile to source features.
4. Planner advisor drafts migration phases from discovery and compatibility evidence after approval.
5. Validation runs deterministic checks against source and target databases.
6. Risk scoring computes axis-aware risk from structured findings and process-control state.
7. Gatekeeper evaluates deterministic readiness predicates.
8. Runbook advisor drafts customer-facing steps with evidence references.
9. Reviewer advisor critiques gaps and may add process-control findings.
10. Eval runner compares detector findings to expected results with model calls disabled.

## Artifact Storage

Markdown and JSON artifacts are sufficient for the MVP. The default implementation writes artifacts under workspace-local directories and snapshots referenced artifacts under each persisted workflow run. It can add database persistence later only if it improves resumability.

Planned artifact groups:

- discovery JSON
- compatibility findings JSON and Markdown
- validation JSON and Markdown
- risk report JSON
- runbook Markdown
- eval report Markdown
- audit log JSONL

## Safety Boundaries

- Compatibility advisory findings cannot block PostgreSQL cutover readiness.
- Cutover readiness reads `migration_integrity` and `process_control` risk only.
- LLM-authored confidence is not accepted as evidence.
- Evidence reference validation confirms citation existence, not semantic proof.
- High-stakes readiness, cutover, rollback, and validation claims are protected by deterministic gate functions.
