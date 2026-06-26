# Agentic Migration Readiness & Validation Platform PRD

## 1. Product Summary

Agentic Migration Validator is a local agentic workflow for assessing database migration readiness, validating post-migration integrity, and generating human-reviewed migration runbooks. It demonstrates how deterministic stages and model-backed advisors can coordinate discovery, compatibility analysis, validation, risk scoring, rollback planning, and customer-facing reporting while keeping humans in control of high-risk decisions.

The MVP will use real PostgreSQL source and target databases to showcase a credible migration workflow. A Snowflake-like target compatibility profile will be used to flag risks that would matter in analytical warehouse migrations without requiring a real Snowflake integration in the first release.

MCP integration is intentionally deferred to phase two. The MVP will use direct Python tool calls through a typed internal tool layer so the same capabilities can later be exposed through MCP.

The central control principle is: advisors propose, deterministic invariants dispose. Model-backed advisors may interpret evidence, draft plans, and critique artifacts, but workflow safety gates must be enforced by pure functions over workflow state. The MVP should use model reasoning only where judgment is genuinely useful; catalog inspection, validation checks, and risk math are deterministic stages, not LLM agents.

## 2. Problem Statement

Enterprise migrations often fail because migration readiness, compatibility checks, validation evidence, rollback planning, and operational ownership are scattered across humans, SQL scripts, tickets, spreadsheets, and undocumented knowledge.

Existing demos of agentic systems often over-index on conversational planning and under-index on inspectability, evidence, and control. This product should show that model-backed advisors can assist with migration reasoning only when their conclusions are grounded in real tool outputs, auditable decisions, and explicit human approvals.

## 3. Goals

- Inspect real PostgreSQL source and target databases.
- Generate a migration readiness report grounded in database evidence.
- Identify compatibility issues using both live database inspection and a Snowflake-like target profile.
- Produce a validation plan with deterministic checks.
- Run post-migration validation checks against source and target databases.
- Generate evidence-backed risk scores.
- Produce a customer-facing migration runbook with rollback guidance.
- Include human approval gates before risky or irreversible recommendations.
- Maintain an audit trail of workflow decisions, tool calls, inputs, outputs, and evidence.
- Include seeded failure scenarios and an evaluation report showing detected, missed, and false-positive findings.

## 4. Non-Goals

- Do not build a production-grade enterprise migration platform.
- Do not perform live production cutovers.
- Do not support every PostgreSQL feature or every target warehouse feature.
- Do not integrate with real Snowflake in the MVP.
- Do not add MCP in phase one.
- Do not rely on LLM-only judgment for readiness, validation, or risk scoring.
- Do not claim a migration is ready unless deterministic validation gates pass and required approvals are present.

## 5. Target Users

- Engineering managers evaluating agentic workflow patterns.
- Data platform engineers assessing migration readiness.
- Solutions architects demonstrating AI-assisted operational workflows.
- Hiring teams looking for evidence of product judgment, agentic architecture, and backend execution quality.

## 6. MVP Scope

### 6.1 Database Setup

The MVP will include Docker-managed PostgreSQL databases:

- `source-postgres`: canonical source database.
- `target-postgres`: migrated target database.

Fixture scenarios will seed both databases with controlled differences.

### 6.2 Target Compatibility Profile

The MVP will include a static compatibility profile, such as `snowflake_like.yml`, to evaluate whether source database features may create risk when migrating to a warehouse-style target.

Compatibility analysis and integrity validation are intentionally separate axes. The MVP validates an actual PostgreSQL-to-PostgreSQL migration, while the compatibility profile provides prospective advisory findings for a hypothetical warehouse-style target. A table can therefore pass Postgres integrity validation while still receiving advisory compatibility findings for features such as `jsonb`, arrays, custom functions, or triggers.

Example rule categories:

- Unsupported features:
  - partial indexes
  - exclusion constraints
  - custom functions
  - triggers
- Risky data types:
  - `jsonb`
  - arrays
  - `money`
  - `interval`
  - timezone-sensitive timestamps
- Precision-sensitive mappings:
  - `numeric`
  - floating-point conversions
  - timestamp conversions

### 6.3 Workflow Stages and Advisors

The system will be built around specialized workflow stages with clear responsibilities, state, artifacts, and handoffs. Some stages are deterministic tool execution. Others are model-backed advisors that synthesize plans, explanations, critiques, and runbooks from deterministic evidence.

| Stage or Advisor | Type | Responsibility |
| --- | --- | --- |
| Discovery Stage | Deterministic | Inspects source schema, tables, indexes, constraints, row counts, nulls, data types, and dependencies. |
| Compatibility Stage | Hybrid | Applies deterministic target-profile rules, then may use model reasoning to explain compatibility implications in plain language. |
| Migration Planner Advisor | Model-backed | Produces migration phases, dependencies, cutover checklist, validation gates, and rollback strategy from structured evidence. |
| Validation Stage | Deterministic | Runs row counts, checksums, full-table comparisons, null distribution checks, referential checks, duplicate checks, and business-rule semantic validation tests. |
| Risk Stage | Deterministic | Generates axis-aware risk scores using a transparent rubric over structured findings and gate state. |
| Runbook Advisor | Model-backed | Writes the final customer-facing runbook, including approval checkpoints and rollback steps. |
| Reviewer Advisor | Model-backed | Provides qualitative critique, flags missing context, and recommends follow-up review. It cannot override deterministic workflow gates. |

This framing is intentional. The product should show that deterministic database work handles facts, arithmetic, and safety gates, while model-backed advisors handle synthesis and communication.

### 6.4 Deterministic Control Model

The workflow must include a deterministic gatekeeper implemented as pure functions over workflow state. These functions enforce safety invariants and cannot be bypassed by advisor output.

Required gatekeeper checks:

- `can_generate_final_plan`: requires discovery artifacts, compatibility findings, and human approval to proceed.
- `can_accept_validation`: requires completed validation checks, resolved evidence references, and human approval.
- `can_recommend_cutover`: requires passed validation, no unresolved blocking findings, resolved evidence references, and human approval.
- `can_recommend_rollback`: requires rollback criteria, failed or blocked validation evidence, and human approval.
- `can_mark_ready`: requires passed validation, no unresolved blocking findings, resolved evidence references, a published runbook, and required human approvals.

The Reviewer Advisor can add critique or request additional review, but it cannot mark an unsafe workflow safe. Conversely, deterministic gates can block readiness even if every advisor recommends proceeding.

### 6.5 Human Approval Gates

The workflow must pause for explicit human approval before:

- Generating the final migration plan.
- Accepting validation results as passed.
- Recommending cutover.
- Recommending rollback.
- Marking the migration as ready.

Approvals should be stored in workflow state and included in the audit log.

### 6.6 Audit Trail

Every workflow stage, advisor, and tool action should emit structured audit events.

Required audit event fields:

- timestamp
- workspace id
- scenario id
- actor name
- actor type
- stage
- tool name, if applicable
- input summary
- output summary
- evidence references
- decision
- severity, where applicable
- confidence basis, only when derived from deterministic evidence such as sample size, rule severity, or validation coverage
- approval status, where applicable

The workflow must validate evidence references before accepting artifacts. Any structured claim in a report, plan, risk explanation, or runbook must reference a tool output, validation result, or audit event. If a reference does not resolve, the artifact is rejected and the workflow remains blocked.

Evidence-reference validation is citation hygiene, not semantic proof. It confirms that a claim points to a real tool output or audit event; it does not prove that the referenced output logically supports the claim. High-stakes claims such as ready, cutover, rollback, and validation passed are protected by deterministic gates. Lower-risk explanatory claims rely on resolved references and reviewer critique, which is useful but weaker.

Structured artifact fields that affect gates or risk scores require field-level evidence references. Narrative sections may use section-level evidence references if every claim in the section is covered by the same referenced evidence.

LLM self-reported confidence is out of scope. Confidence-like fields may only be used when they are derived from deterministic inputs.

### 6.7 Structured Findings

Findings are the shared contract between detectors, risk scoring, gatekeeper checks, evals, reports, and the UI. Every detector must emit findings with stable identity keys.

Required finding fields:

```json
{
  "record_type": "detector_finding",
  "risk_axis": "migration_integrity",
  "finding_key": "validation.checksum_mismatch:public.orders:*",
  "finding_type": "validation.checksum_mismatch",
  "detector": "canonical_checksum",
  "severity": "high",
  "status": "unresolved",
  "gate_effect": ["blocks_cutover", "blocks_ready"],
  "scope": {
    "schema": "public",
    "table": "orders",
    "column": null,
    "constraint": null,
    "business_key": null
  },
  "blast_radius": {
    "affected_tables": 1,
    "affected_rows": 12,
    "source_rows": 1200,
    "affected_row_percent": 1.0,
    "critical_path": true
  },
  "base_points": 35,
  "risk_points": 53,
  "evidence_refs": ["tool.validation.checksum.orders.v1"],
  "summary": "Canonical checksum mismatch for public.orders."
}
```

The `finding_key` is the eval identity key for detector findings. It must be deterministic and should be composed from `finding_type`, schema, table, column, constraint, and business key where applicable.

Finding taxonomy:

- `detector_finding`: emitted by deterministic detectors such as schema diff, checksum, row count, null distribution, duplicate checks, referential checks, and compatibility rules. These records are eligible for detection eval matching.
- `gate_finding`: emitted from workflow or artifact state, such as missing approval, missing rollback criteria, or unresolved evidence references. These records affect process risk and gates but are excluded from detector eval matching.
- `derived_risk_factor`: computed by the Risk Stage from other findings or gate state, such as compounding multiple high-severity validation failures. These records can carry their own severity or explain escalation, but they do not create duplicate detector findings.

Key namespaces:

- Detector findings use domain prefixes such as `validation.*`, `schema.*`, and `compatibility.*`.
- Gate findings use `gate.*` or `artifact.*`.
- Derived risk factors use `risk.derived.*`.

Risk axes:

- `migration_integrity`: risks to the actual PostgreSQL-to-PostgreSQL migration being validated.
- `compatibility_advisory`: prospective risks against the Snowflake-like warehouse profile.
- `process_control`: risks from missing approvals, missing rollback criteria, unresolved evidence, or other workflow state.

Compatibility advisory findings must never carry readiness-blocking gate effects such as `blocks_cutover` or `blocks_ready`. They may request advisory review or appear in the compatibility advisory score, but they cannot block PostgreSQL cutover readiness. Cutover readiness is governed by `migration_integrity` and `process_control` only.

Detection evals compare only `record_type: "detector_finding"` records. Gate findings and derived risk factors must not appear in `expected_findings` unless a separate process-control eval is explicitly added.

Severity enum:

- `info`: context only; no risk points.
- `low`: advisory issue; does not block gates.
- `moderate`: requires review or remediation; does not block gates by itself.
- `high`: unresolved issue blocks cutover or readiness when `gate_effect` says so.
- `critical`: unresolved issue blocks cutover and readiness, sets a Critical risk floor, and requires explicit remediation or accepted-risk handling.

A blocking finding is any unresolved finding whose `gate_effect` includes the gate being evaluated. A critical finding is any unresolved finding with `severity: "critical"`. Critical findings are always blocking, but high findings can also be blocking when their `gate_effect` requires it.

Critical severity can be emitted by a single detector when blast radius is high enough, such as unexplained missing rows above 10% of a critical-path table, failed checksums across multiple critical-path tables, or schema drift that removes a primary key from a critical table and prevents validation. Critical can also be reached by compounding multiple high-severity findings in the risk stage.

The 2.0 blast-radius tier escalates unresolved high-severity `migration_integrity` validation findings to `critical`. This covers cases such as missing rows across five or more tables, even when no individual table is marked as critical path. This escalation does not apply to `compatibility_advisory` findings.

Derived escalation replaces or annotates existing findings; it does not add duplicate detector points. For example, missing rows affecting 15% of a critical-path table remains one `validation.missing_rows` detector finding whose severity is escalated to `critical`. It is not scored once as missing rows and again as a separate critical blast-radius validation failure.

### 6.8 Artifacts

The MVP should generate:

- migration readiness report
- compatibility findings report
- validation report
- risk report JSON
- customer-facing runbook
- eval report
- audit log JSON

Markdown and JSON are sufficient for the MVP. PDF export is optional after the core workflow is stable.

## 7. Core User Experience

The application should open directly into a migration workspace, not a marketing landing page.

Primary UI sections:

- Migration Workspace:
  - source database
  - target database
  - scenario
  - current stage
- Workflow Timeline:
  - discovery
  - compatibility
  - planning
  - validation
  - risk
  - review
  - runbook
- Findings:
  - severity
  - evidence
  - affected tables
  - suggested action
- Validation:
  - row counts
  - checksums
  - null distributions
  - full-table comparisons
  - referential checks
- Runbook:
  - pre-migration checklist
  - migration sequence
  - validation gates
  - rollback plan
  - approval checkpoints
- Audit Log:
  - actor
  - tool call
  - input
  - output
  - decision
  - evidence

## 8. Functional Requirements

### 8.1 Database Introspection

The system must inspect:

- schemas
- tables
- columns
- data types
- nullable columns
- primary keys
- foreign keys
- unique constraints
- check constraints
- indexes
- row counts
- table dependencies
- views, where feasible

### 8.2 Schema Comparison

The system must detect:

- missing tables
- extra tables
- missing columns
- extra columns
- changed data types
- changed nullability
- missing primary keys
- missing foreign keys
- missing unique constraints
- index differences

### 8.3 Data Validation

The system must run:

- row count comparisons
- table-level checksums
- full-table row comparisons for MVP fixtures
- null distribution checks
- duplicate checks on configured keys
- referential integrity checks
- business-rule semantic checks defined by scenario fixtures

The MVP uses full-table validation against small seeded fixtures. Row counts, checksums, null counts, duplicates, and referential checks should therefore be exact. Thresholds default to zero tolerance unless a scenario explicitly encodes an allowed lag or accepted drift. Sampling, partitioned comparison, and probabilistic thresholds are production-scaling paths, not MVP behavior.

Semantic checks are business-rule invariants, not vague AI judgment. Examples include:

- order line item totals must equal order totals
- payment amounts must be non-negative
- active subscriptions must reference active customers
- closed invoices must have a closed timestamp

Checksums must avoid false positives caused by database formatting differences. The checksum implementation must use order-independent aggregation of per-row hashes with explicit type canonicalization.

Required checksum canonicalization rules:

- Select a deterministic column set and order columns by name.
- Use primary key or configured business key fields to identify rows.
- Encode `NULL` with an explicit sentinel distinct from empty strings.
- Normalize numeric values with decimal-aware formatting, preserving declared scale when relevant.
- Normalize timestamps to UTC ISO 8601 with explicit precision.
- Serialize JSON values with sorted keys and stable whitespace.
- Encode booleans, arrays, and enums with stable typed representations.
- Hash canonical row payloads, then compute table-level digests by sorting row hashes before aggregation.
- Record the canonicalization version in validation evidence.

The `failed_checksum` scenario is only valid if row counts and schemas match and the checksum is the primary detector.

### 8.4 Compatibility Analysis

The system must flag:

- unsupported database features
- risky data types
- precision loss risks
- timestamp conversion risks
- unsupported SQL patterns in views or functions, where feasible
- target profile violations

### 8.5 Risk Scoring

Risk scoring must be evidence-based and axis-aware. The system must not collapse PostgreSQL migration integrity and Snowflake-like compatibility advisory findings into one undifferentiated score.

Inputs should include:

- `migration_integrity` findings:
  - validation failures
  - schema drift between source and target
  - missing constraints in the target
  - data quality issues
  - blast radius by affected table count, row count, row percentage, and critical-path status
- `compatibility_advisory` findings:
  - risky source database features under the Snowflake-like target profile
  - precision or timestamp conversion concerns
  - unsupported SQL patterns in views or functions
- `process_control` findings:
  - unresolved approval gates
  - missing rollback criteria
  - unresolved evidence references
  - deterministic gate blocks
  - reviewer critiques, as non-gating qualitative inputs

Risk output should include:

- migration integrity score and band
- compatibility advisory score and band
- process control score, band, and findings
- readiness gate status
- top contributing factors
- evidence references
- recommended next actions

Risk bands:

- 0-24: Low
- 25-49: Moderate
- 50-74: High
- 75-100: Critical

PostgreSQL cutover readiness is based on `migration_integrity` and `process_control`. `compatibility_advisory` is reported separately and must not make a clean PostgreSQL-to-PostgreSQL migration appear riskier than it is. This preserves the two-axis design: did the migration being validated succeed, and what should the team know before considering a warehouse target?

Risk scoring must use a transparent gate-plus-additive rubric with severity as the single source of band floors.

Formula:

```text
risk_points = round_half_up(min(base_points * blast_radius_multiplier + instance_bonus, per_finding_cap))
axis_raw_score = sum(risk_points for each unresolved risk item in the axis)
axis_floor = max(severity_floor(item.severity) for each unresolved risk item in the axis)
axis_score = round_half_up(clamp(max(axis_raw_score, axis_floor), 0, 100))
```

Severity floors:

- `info`: 0
- `low`: 0
- `moderate`: 25
- `high`: 50
- `critical`: 75

The implementation must use decimal round-half-up behavior, not Python's default banker's rounding. For example, `35 * 1.5 = 52.5` becomes `53`.

Blast radius multiplier:

| Condition | Multiplier |
| --- | ---: |
| Default single-object finding with no row impact | 1.0 |
| Affects at least 1,000 rows, more than 0.1% of a table, or two tables | 1.25 |
| Affects at least 100,000 rows, more than 1% of a table, or a critical-path object | 1.5 |
| Affects at least 1,000,000 rows, more than 10% of a table, or five or more tables | 2.0 |

Per-finding scores should be capped at 2x the base points unless the finding has `severity: "critical"`.

The cap applies after multiplier and instance bonus:

```text
per_finding_cap = 2 * base_points
risk_points = round_half_up(min(base_points * blast_radius_multiplier + instance_bonus, per_finding_cap))
```

At the highest blast-radius tier, `base_points * 2.0` already equals the cap, so the instance bonus may be absorbed. This is deliberate. The cap prevents a single finding from running away; true escalation should happen through severity or `derived_risk_factor` records.

Instance bonus:

- Add 2 points for each additional affected table after the first, capped at 10.
- Add 1 point for each additional affected column, constraint, or business key after the first, capped at 5.
- Do not apply instance bonuses to findings that already use row-percentage blast radius unless the finding spans multiple tables.

Initial detector base points:

| Record Type | Risk Axis | Evidence Type | Severity | Base Points |
| --- | --- | --- | --- | ---: |
| `detector_finding` | `migration_integrity` | Failed checksum with matching row counts and schema | `high` | 35 |
| `detector_finding` | `migration_integrity` | Broken referential integrity | `high` | 35 |
| `detector_finding` | `migration_integrity` | Missing rows not explained by replication lag | `high` | 30 |
| `detector_finding` | `migration_integrity` | High-impact schema drift, such as missing required table or primary key | `high` | 25 |
| `detector_finding` | `migration_integrity` | Missing unique or foreign key constraint | `moderate` | 15 |
| `detector_finding` | `migration_integrity` | Precision-sensitive target type change | `moderate` | 15 |
| `detector_finding` | `migration_integrity` | Exact null distribution mismatch | `moderate` | 12 |
| `detector_finding` | `migration_integrity` | Duplicate records on configured business key | `high` | 20 |
| `detector_finding` | `migration_integrity` | Explained replication lag with known cutoff | `info` | 0 |
| `detector_finding` | `compatibility_advisory` | Unsupported target-profile feature in critical path | `moderate` | 20 |
| `detector_finding` | `compatibility_advisory` | Unsupported target-profile feature outside critical path | `low` | 8 |
| `detector_finding` | `compatibility_advisory` | Precision or timestamp risk under warehouse profile | `low` | 8 |

Initial process-control base points:

| Record Type | Risk Axis | Evidence Type | Severity | Base Points |
| --- | --- | --- | --- | ---: |
| `gate_finding` | `process_control` | Human approval missing for required gate | `moderate` | 10 |
| `gate_finding` | `process_control` | Runbook missing rollback criteria | `high` | 20 |
| `gate_finding` | `process_control` | Unresolved evidence reference in generated artifact | `high` | 25 |
| `gate_finding` | `process_control` | Qualitative reviewer critique | `low` to `high` | 0-10 |

Derived risk factors:

| Record Type | Risk Axis | Condition | Effect |
| --- | --- | --- | --- |
| `derived_risk_factor` | `migration_integrity` | Single validation finding has critical blast radius | Escalate that finding to `severity: "critical"`; do not add a separate detector score. |
| `derived_risk_factor` | `migration_integrity` | Two or more unresolved high-severity validation findings | Emit `risk.derived.compounding_high_validation_failures` with `severity: "critical"` and zero base points; do not duplicate detector points. |

Critical findings must gate readiness even if the additive score is numerically low. Critical is reachable either from a single critical-severity finding or from compounding high-severity findings. This is intentional: a small orphaned-key issue may be High, while broad unexplained data loss or multiple simultaneous integrity failures becomes Critical.

### 8.6 Deterministic Guardrails and Reviewer Role

The deterministic gatekeeper must block:

- readiness claims without successful validation evidence
- cutover recommendations with unresolved blocking findings
- rollback recommendations without stated rollback criteria
- risk scores without evidence
- runbooks missing human approval checkpoints
- artifacts with unresolved evidence references

The Reviewer Advisor must critique:

- unsupported assumptions
- unclear ownership
- missing remediation steps
- incomplete rollback criteria
- weak or overbroad conclusions
- cases where evidence exists but the recommendation is operationally risky

Reviewer critiques can add findings, request human review, or increase qualitative risk factors, but they cannot override deterministic gatekeeper blocks.

## 9. Evaluation Dataset

The MVP will include seeded scenarios:

Each scenario should isolate one primary detector wherever possible. This makes the eval report useful because it shows which check caught which intended failure. Overlapping failures should be avoided unless the scenario explicitly tests multi-factor risk.

| Scenario | Primary Detector | Failure Mode |
| --- | --- | --- |
| `clean_migration` | Baseline validation | Expected to pass validation with low migration-integrity risk. |
| `missing_rows` | Row count comparison | Target is missing records from one or more tables. |
| `schema_drift` | Schema comparison | Target schema differs from source schema. |
| `bad_types` | Schema comparison | Target changes precision-sensitive or incompatible data types. |
| `broken_fk` | Referential integrity check | Target contains orphaned foreign key references. |
| `null_distribution_change` | Null distribution check | Target null rates differ materially from source. |
| `duplicate_records` | Duplicate business-key check | Target contains duplicate records for configured business keys. |
| `failed_checksum` | Canonical checksum | Source and target row counts and schemas match, but content differs. |
| `unsupported_sql` | Target compatibility profile | Source uses functions or patterns flagged by the Snowflake-like profile. |
| `replication_lag` | Lag-aware row freshness check | Target intentionally trails source by a known cutoff timestamp. |

`replication_lag` must be distinct from `missing_rows`. Missing rows indicate unexplained data loss, while replication lag indicates the target is behind a known cutoff. The product should surface this distinction because it maps to a real cutover decision: wait, catch up, or investigate.

The `clean_migration` scenario must define its expected finding set explicitly. Its `migration_integrity` expected findings should be empty. If the clean fixture intentionally includes source features that trigger Snowflake-like advisory findings, those findings must be listed as `compatibility_advisory` expected findings or as allowed extra findings so they do not count as false positives.

The `replication_lag` scenario must emit an expected `validation.replication_lag` detector finding with `risk_axis: "migration_integrity"`, `severity: "info"` or `severity: "low"`, no gate effect, and evidence for the known cutoff timestamp. It must not emit `validation.missing_rows` unless rows are missing beyond the explained cutoff.

The eval report must show:

- expected finding
- detected finding
- missed finding
- false positive
- severity
- evidence source

Detection evals must run with model calls disabled. The eval runner should score deterministic findings from tools and rule-based stages only. LLM-authored planner, runbook, compatibility explanation, and reviewer prose can be reviewed separately as qualitative artifacts, but they should not affect deterministic detected/missed/false-positive metrics.

Expected-results format:

```json
{
  "scenario_id": "failed_checksum",
  "model_calls": "disabled",
  "expected_findings": [
    {
      "record_type": "detector_finding",
      "risk_axis": "migration_integrity",
      "finding_key": "validation.checksum_mismatch:public.orders:*",
      "finding_type": "validation.checksum_mismatch",
      "detector": "canonical_checksum",
      "severity": "high",
      "scope": {
        "schema": "public",
        "table": "orders",
        "column": null,
        "constraint": null,
        "business_key": null
      },
      "expected_gate_effect": ["blocks_cutover", "blocks_ready"]
    }
  ],
  "allowed_extra_findings": []
}
```

Clean migration example:

```json
{
  "scenario_id": "clean_migration",
  "model_calls": "disabled",
  "expected_findings": [],
  "allowed_extra_findings": []
}
```

Replication lag example:

```json
{
  "scenario_id": "replication_lag",
  "model_calls": "disabled",
  "expected_findings": [
    {
      "record_type": "detector_finding",
      "risk_axis": "migration_integrity",
      "finding_key": "validation.replication_lag:public.orders:*",
      "finding_type": "validation.replication_lag",
      "detector": "lag_aware_row_freshness",
      "severity": "info",
      "scope": {
        "schema": "public",
        "table": "orders",
        "column": null,
        "constraint": null,
        "business_key": null
      },
      "expected_gate_effect": [],
      "known_cutoff": "fixture-defined"
    }
  ],
  "allowed_extra_findings": []
}
```

Eval matching rules:

- Detected: produced finding has the same `finding_key` as an expected finding.
- Missed: expected finding has no produced finding with the same `finding_key`.
- False positive: produced finding key is absent from both `expected_findings` and `allowed_extra_findings`.
- Severity mismatch: produced finding key matches but severity differs.
- Scope mismatch: produced finding key matches but scope fields differ.
- Axis mismatch: produced finding key matches but `risk_axis` differs.

This makes eval comparison a set operation over stable finding keys rather than a subjective comparison of prose.

## 10. Suggested Technical Architecture

### 10.1 Phase One Architecture

```text
Vite React UI
        |
FastAPI backend
        |
Deterministic stages and model-backed advisors
        |
Python tool registry
        |
PostgreSQL source and target
        |
JSON and Markdown artifacts
```

### 10.2 Tool Layer

Tools should be implemented as plain Python functions with typed inputs and outputs.

Initial tool modules:

- `db_introspection.py`
- `schema_diff.py`
- `compatibility_rules.py`
- `data_validation.py`
- `checksum.py`
- `risk_scoring.py`
- `report_writer.py`
- `audit_log.py`

The tool interface should remain stable enough that these same tools can be exposed through MCP in phase two.

Database tools must use read-only roles for both source and target databases. Model-backed advisors should never receive raw connection strings and should never mutate databases directly. All database access should go through typed tools with scoped permissions.

### 10.3 Workflow Orchestration

Preferred MVP direction: LangGraph-first.

Rationale:

- The workflow is stateful and staged.
- Human approval gates are central to the product.
- Resumable execution is a strong fit for migration workflows.
- Workflow state should be inspectable before continuing.

Humans may edit workflow inputs, scenario configuration, approvals, and accepted-risk decisions. These edits must be logged as audit events. Humans cannot directly set gate outputs such as `can_mark_ready`; gates always recompute from current state.

OpenAI Agents SDK remains a strong alternative or phase-two enhancement for built-in agent concepts, guardrails, tracing, tools, handoffs, and MCP integration.

### 10.4 Model Call, Cost, and Latency Budget

The MVP should keep model usage bounded so the workflow feels intentional rather than chatty.

Target budget per scenario run:

- Target of 3-4 model calls for a full workflow.
- Maximum of 6 model calls including retries.
- Discovery, schema comparison, validation, detection, and risk math must be deterministic tool work.
- Model calls should be reserved for plan synthesis, runbook drafting, compatibility explanation, and qualitative review.
- The UI should expose when a stage used model reasoning versus deterministic tooling.
- Each model-generated claim must reference resolved evidence before the artifact is accepted.

## 11. Phase Two Scope

MCP will be introduced after the core product loop is working.

Phase two capabilities:

- MCP server exposing database inspection and validation tools.
- MCP client integration in the workflow.
- MCP tool-call audit events.
- Optional external tool integrations:
  - Jira
  - ServiceNow
  - GitHub
  - Datadog
  - S3
  - Snowflake
- Optional ChatGPT app or other MCP-compatible client.

Phase two positioning:

> Model-backed advisors operate through governed tools rather than raw database access, and the same validation capabilities can be shared across agentic clients through MCP.

## 12. Timeline

### Day 1: Product and Repo Foundation

- Finalize PRD and MVP boundaries.
- Create repo structure.
- Define scenario format.
- Define artifact schemas.
- Define audit event schema.
- Define human approval gates.
- Define deterministic gatekeeper invariants.
- Define evidence-reference schema.
- Define structured finding taxonomy, severity enum, and risk axes.

Deliverables:

- README draft
- architecture doc
- fixture plan
- initial API contract
- gatekeeper invariant spec
- evidence-reference spec
- structured finding schema with `record_type`, `risk_axis`, and `finding_key`

### Days 2-3: PostgreSQL Fixtures and Tooling

- Add Docker Compose for source and target PostgreSQL.
- Add read-only database roles for validation tools.
- Create seed scripts.
- Implement initial fixture scenarios.
- Build database introspection tools.
- Build schema comparison tools.
- Build row count and canonical checksum validators.
- Emit structured findings from deterministic detectors.

Deliverables:

- local Postgres environment
- seedable source and target databases
- first deterministic tool outputs
- canonical checksum implementation
- read-only database access path
- structured detector findings

### Days 4-5: Workflow Orchestration

- Implement workflow state model.
- Implement Discovery Stage.
- Implement Compatibility Stage.
- Implement Validation Stage.
- Implement Risk Stage.
- Implement Planner, Runbook, and Reviewer Advisor stubs.
- Emit audit events from every workflow step.
- Require evidence references in generated artifacts.

Deliverables:

- CLI or API-triggered workflow
- structured workflow artifacts
- audit log output
- evidence-linked report artifacts

### Day 6: Human Approval Gates and Guardrails

- Add approval states.
- Pause workflow before risky stages.
- Add deterministic gatekeeper functions.
- Add reviewer critique logic.
- Add evidence-reference validation.
- Evaluate gates from structured finding statuses and `gate_effect`.
- Prevent readiness claims without validation evidence.

Deliverables:

- resumable workflow
- approval API endpoints
- deterministic gatekeeper test cases
- reviewer critique examples
- rejected artifact examples

### Days 7-8: Frontend Dashboard

- Build Vite React migration workspace view.
- Build workflow timeline.
- Build findings table.
- Build validation panel.
- Build runbook preview.
- Build audit log view.
- Add approval controls.

Deliverables:

- working local dashboard
- complete demo path for at least three scenarios

### Day 9: Evaluation Harness

- Add expected results fixtures.
- Implement eval runner.
- Generate eval table.
- Compare detected, missed, and false-positive findings.
- Confirm each scenario isolates its primary detector.
- Include lag-aware distinction between missing rows and replication lag.
- Pin expected findings for `clean_migration` and `replication_lag`.
- Run detection evals with model calls disabled.

Deliverables:

- `eval_report.md`
- scenario coverage table
- repeatable eval command
- detector coverage matrix
- expected-results JSON schema
- explicit clean and replication-lag expected-results fixtures

### Day 10: Documentation and Demo Polish

- Finalize README.
- Add architecture diagram.
- Add sample reports.
- Add demo script.
- Add out-of-scope section.
- Lead the demo with the failed-checksum scenario.
- Explain the reusable pattern: deterministic invariants with LLM advisors on top.
- Explain the evidence boundary: resolved references prevent fabricated citations, while deterministic gates protect high-stakes claims.
- Record or prepare demo walkthrough.

Deliverables:

- portfolio-ready repo
- demo script
- sample artifacts

## 13. Success Metrics

The MVP is successful when:

- A user can start the app locally with documented commands.
- The system can inspect two live PostgreSQL databases.
- The system can detect seeded migration failures.
- Each workflow stage produces structured artifacts.
- Detection evals run with model calls disabled.
- Structured findings have stable identity keys.
- Structured findings separate detector findings, gate findings, and derived risk factors.
- Risk reports separate migration integrity, compatibility advisory, and process control.
- Compatibility advisory findings cannot carry readiness-blocking gate effects.
- The audit log shows tools called, evidence used, and decisions made.
- The deterministic gatekeeper blocks unsupported readiness claims.
- Generated artifacts are rejected when evidence references do not resolve.
- Validation tools use read-only database access.
- The UI shows workflow state and human approval gates.
- The eval report clearly shows detected, missed, and false-positive cases.
- The README explains what is in scope and what is intentionally deferred.
- The README teaches the reusable agentic pattern, not only the migration tool.
- The README distinguishes evidence-reference resolution from semantic claim verification.

## 14. Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| PostgreSQL setup slows development. | Use Docker Compose with health checks and deterministic seed scripts. |
| Advisor outputs become vague. | Require structured artifacts, resolved evidence references, and artifact validation. |
| UI grows too large. | Use Vite React and keep the UI focused on workflow state, findings, validation, runbook, and audit log. |
| Compatibility analysis becomes too broad. | Use a clearly bounded Snowflake-like target profile. |
| Evals become brittle. | Use deterministic fixtures, structured finding keys, and expected results JSON. |
| LLM claims exceed evidence. | Deterministic evidence validation and gatekeeper functions reject unsupported claims. |
| Checksum validation creates false positives. | Use canonical type encoding and order-independent row-hash aggregation. |
| Risk scoring feels arbitrary. | Use a transparent gate-plus-additive rubric with severity-derived floors. |
| Humans bypass gate state while editing workflow state. | Log all state edits and recompute gates from state instead of storing editable gate outputs. |
| MCP distracts from MVP. | Design the tool layer for MCP compatibility but defer protocol implementation. |

## 15. Open Questions

- Should the MVP use LangGraph only, or leave room for an OpenAI Agents SDK variant?
- Should generated artifacts be stored on disk, in Postgres, or both?
- Should the first version include generated Markdown only, or also PDF export?
- Should the first implementation include the model-backed Compatibility explanation, or keep Compatibility fully deterministic until the core loop is stable?

## 16. Recommended MVP Demo Path

The strongest first demo should show three scenarios:

1. Failed checksum:
   - Row counts match.
   - Schemas match.
   - Canonical checksums fail.
   - Validation Stage marks silent content divergence.
   - Deterministic gatekeeper blocks cutover.
   - Runbook recommends rollback or remediation path.
   - Audit log shows the evidence chain.

2. Clean migration:
   - Discovery succeeds.
   - Compatibility produces low-severity findings only.
   - Validation passes.
   - Migration integrity risk is low.
   - Compatibility advisory findings, if present, are shown separately.
   - Human approves readiness.

3. Schema drift:
   - Compatibility detects target schema differences.
   - Risk increases.
   - Deterministic gatekeeper blocks readiness until drift is resolved or explicitly accepted.
   - Reviewer Advisor adds qualitative critique about operational ownership and remediation.

This path demonstrates why agentic migration validation needs real tools, evidence, auditability, and human control.
