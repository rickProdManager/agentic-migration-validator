# Structured Finding Schema

Findings are the shared contract between detectors, risk scoring, gatekeeper checks, evals, reports, and the UI. Every detector finding must have a deterministic identity key.

## Record Types

| Record Type | Purpose | Detection Eval Eligible |
| --- | --- | --- |
| `detector_finding` | Emitted by deterministic detectors such as schema diff, checksum, row count, null distribution, duplicate checks, referential checks, and compatibility rules. | Yes |
| `gate_finding` | Emitted from workflow or artifact state, such as missing approval or unresolved evidence references. | No |
| `derived_risk_factor` | Computed by the risk stage from other findings or gate state, such as compounding high-severity validation failures. | No |

## Risk Axes

| Risk Axis | Meaning | Can Block PostgreSQL Cutover |
| --- | --- | --- |
| `migration_integrity` | Risk to the actual PostgreSQL-to-PostgreSQL migration being validated. | Yes |
| `compatibility_advisory` | Prospective risk against the Snowflake-like warehouse profile. | No |
| `process_control` | Risk from missing approvals, unresolved evidence, rollback gaps, and workflow governance. | Yes |

Compatibility advisory findings must never carry readiness-blocking gate effects such as `blocks_cutover` or `blocks_ready`.

## Severity Enum

| Severity | Meaning | Floor |
| --- | --- | ---: |
| `info` | Context only. | 0 |
| `low` | Advisory issue. | 0 |
| `moderate` | Requires review or remediation, but does not block by itself. | 25 |
| `high` | Blocks when unresolved and a matching gate effect is present. | 50 |
| `critical` | Always blocks cutover and readiness while unresolved. | 75 |

## Required Fields

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

## Field Rules

- `finding_key` is the stable eval identity key for detector findings.
- `finding_type` should use a namespaced prefix such as `validation.*`, `schema.*`, `compatibility.*`, `gate.*`, `artifact.*`, or `risk.derived.*`.
- `status` is one of `unresolved`, `resolved`, `accepted_risk`, or `not_applicable`.
- `gate_effect` may include `blocks_plan`, `blocks_validation_acceptance`, `blocks_cutover`, `blocks_rollback`, or `blocks_ready`.
- `evidence_refs` must resolve to known tool outputs, validation results, artifacts, or audit events before an artifact can be accepted.
- Detector findings should include enough `scope` fields to make eval matching deterministic.

## Finding Key Format

Use this format unless a detector has a stronger domain-specific key:

```text
{finding_type}:{schema}:{table}:{column_or_constraint_or_business_key}
```

Examples:

```text
validation.checksum_mismatch:public.orders:*
schema.missing_primary_key:public.orders:orders_pkey
validation.duplicate_business_key:public.customers:email
compatibility.unsupported_feature:public.orders:trigger:update_order_total
```

## Eval Matching

Detection evals compare only `record_type: "detector_finding"` records.

- Detected: produced finding has the same `finding_key` as an expected finding.
- Missed: expected finding has no produced finding with the same `finding_key`.
- False positive: produced finding key is absent from both `expected_findings` and `allowed_extra_findings`.
- Severity mismatch: produced finding key matches but severity differs.
- Scope mismatch: produced finding key matches but scope differs.
- Axis mismatch: produced finding key matches but `risk_axis` differs.

