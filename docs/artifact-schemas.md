# Artifact Schemas

Artifacts are structured outputs produced by workflow stages and advisors. The MVP may store them as JSON and Markdown files.

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

The runbook may be Markdown with structured front matter.

```json
{
  "metadata": {},
  "title": "Migration Runbook: failed_checksum",
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
  ]
}
```

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

