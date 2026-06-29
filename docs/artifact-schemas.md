# Artifact Schemas

Artifacts are structured outputs produced by workflow stages and advisors. The MVP may store them as JSON and Markdown files.

The local artifact writer stores reproducible demo outputs under `artifacts/`:

```text
artifacts/
  evidence_registry.json
  eval_report.json
  manifest.json
  scenarios/
    failed_checksum/
      runbook.json
```

The `artifacts/` directory is intentionally ignored by git. The committed source contains the writer, validators, and tests; generated outputs can be reproduced from Docker fixtures.

## Common Artifact Metadata

```json
{
  "artifact_id": "artifact.validation_report.v1",
  "workspace_id": "workspace_demo",
  "scenario_id": "failed_checksum",
  "artifact_type": "validation_report",
  "format": "json",
  "status": "accepted",
  "created_at": "2026-06-25T12:00:00Z",
  "producer": "validation_stage",
  "model_calls": "disabled",
  "evidence_refs": ["validation.checksum.public_orders.v1"],
  "content_hash": "sha256:example"
}
```

Allowed `status` values:

- `draft`
- `rejected`
- `accepted`
- `published`

The `content_hash` is calculated over the JSON artifact with `metadata.content_hash` excluded. Any post-generation edit must be followed by revalidation or regeneration.

## Discovery Artifact

```json
{
  "metadata": {},
  "schemas": [
    {
      "schema": "public",
      "tables": [
        {
          "table": "orders",
          "columns": [],
          "primary_key": ["id"],
          "foreign_keys": [],
          "unique_constraints": [],
          "indexes": [],
          "row_count": 1200
        }
      ]
    }
  ],
  "evidence_refs": ["tool.discovery.public_orders.v1"]
}
```

## Compatibility Report

```json
{
  "metadata": {},
  "target_profile": "snowflake_like",
  "findings": [],
  "summary": {
    "highest_severity": "moderate",
    "advisory_review_required": true
  },
  "evidence_refs": ["tool.compatibility.snowflake_like.v1"]
}
```

## Validation Report

```json
{
  "metadata": {},
  "checks": [
    {
      "check_id": "validation.checksum.public_orders.v1",
      "check_type": "checksum",
      "scope": {
        "schema": "public",
        "table": "orders"
      },
      "status": "failed",
      "evidence_ref": "validation.checksum.public_orders.v1",
      "findings": ["validation.checksum_mismatch:public.orders:*"]
    }
  ],
  "overall_status": "failed"
}
```

Allowed check statuses:

- `passed`
- `failed`
- `blocked`
- `skipped`

## Risk Report

```json
{
  "metadata": {},
  "axes": {
    "migration_integrity": {
      "score": 75,
      "band": "critical",
      "raw_score": 60,
      "floor": 75
    },
    "compatibility_advisory": {
      "score": 0,
      "band": "low",
      "raw_score": 0,
      "floor": 0
    },
    "process_control": {
      "score": 25,
      "band": "moderate",
      "raw_score": 10,
      "floor": 25
    }
  },
  "cutover_ready_risk_axes": ["migration_integrity", "process_control"],
  "top_contributing_findings": []
}
```

## Runbook

The runbook may be Markdown with structured front matter or a structured JSON draft. Advisor-generated runbooks must follow `docs/runbook-advisor-boundary.md`.

```json
{
  "metadata": {},
  "title": "Migration Runbook: failed_checksum",
  "model_calls": "disabled",
  "claims": [
    {
      "claim_key": "ready_blocked",
      "claim_type": "recommendation",
      "claim": "Do not mark the migration ready while can_mark_ready is blocked.",
      "evidence_refs": ["gate.can_mark_ready.failed_checksum.v1"],
      "finding_keys": ["validation.checksum_mismatch:public.customers:*"]
    }
  ],
  "sections": [
    {
      "section_id": "rollback",
      "title": "Rollback Criteria",
      "body_markdown": "Rollback if checksum mismatch remains unresolved.",
      "evidence_refs": ["validation.checksum.public_orders.v1"]
    }
  ],
  "approval_checkpoints": [
    "final_plan",
    "validation_acceptance",
    "cutover_recommendation",
    "readiness"
  ],
  "boundary_validation": {
    "passed": true,
    "issues": []
  }
}
```

Runbook drafts may set `model_calls` to `enabled` only when live prose has been added and boundary validation passes.

## Eval Report

```json
{
  "metadata": {},
  "model_calls": "disabled",
  "scenarios": [
    {
      "scenario_id": "failed_checksum",
      "detected": [],
      "missed": [],
      "false_positives": [],
      "severity_mismatches": [],
      "scope_mismatches": [],
      "axis_mismatches": []
    }
  ]
}
```

## Evidence Registry

The evidence registry resolves evidence references used by generated artifacts to concrete artifact bundle entries.

```json
{
  "metadata": {},
  "registry_version": "evidence_registry.v1",
  "entry_count": 1,
  "entries": [
    {
      "evidence_ref": "validation.checksum.public.customers.v1",
      "workspace_id": "workspace_demo",
      "scenario_id": "failed_checksum",
      "source_type": "validation_result",
      "stage": "validation",
      "producer": "eval_runner",
      "source_artifact_id": "artifact.eval_report.fixture_suite.v1",
      "source_artifact_path": "eval_report.json",
      "content_hash": "sha256:example"
    }
  ]
}
```

## Artifact Validation

Generated artifacts must pass deterministic validation before they are written:

- Common metadata fields are present.
- `format` is `json`.
- `status` and `model_calls` use known values.
- `metadata.evidence_refs` is present and non-empty.
- `metadata.content_hash` matches the artifact content.
- Runbook artifacts include `boundary_validation.passed=true`.
- Runbook claims include claim-level evidence refs.
- Eval report artifacts include scenario results, gate results, and matching `scenario_count`.
- Evidence registry artifacts include unique entries with source artifact pointers.
- When an evidence registry is present, non-registry artifact metadata evidence refs must resolve to registry entries.
