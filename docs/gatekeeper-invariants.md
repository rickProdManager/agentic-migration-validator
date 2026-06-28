# Gatekeeper Invariants

The deterministic gatekeeper is a set of pure functions over workflow state. Advisors may recommend actions, but only gatekeeper functions decide whether the workflow may proceed.

## Implemented MVP Slice

The current implementation lives in `tools/gatekeeper.py` and evaluates the two PostgreSQL MVP readiness gates used by fixture evals:

- `can_recommend_cutover`
- `can_mark_ready`

The scenario eval runner uses an approval-satisfied fixture context so the report isolates detector-driven gate behavior:

- `clean_migration` is allowed.
- `schema_drift` is allowed because low structural findings and compatibility advisories do not block cutover/readiness.
- `failed_checksum` is blocked by `validation.checksum_mismatch`.
- `schema_relaxed_unique_violation` is blocked by checksum mismatch and the high duplicate-values validation finding.

## Gate Inputs

Gate functions read:

- stage completion status
- structured findings
- validation results
- resolved evidence references
- generated artifact status
- human approvals
- rollback criteria
- accepted-risk decisions

Gate functions do not read free-form advisor prose except through structured findings or validated artifact fields.

## Gate Effects

Findings may carry these gate effects:

| Gate Effect | Meaning |
| --- | --- |
| `blocks_plan` | Blocks final migration plan generation. |
| `blocks_validation_acceptance` | Blocks accepting validation results as passed. |
| `blocks_cutover` | Blocks cutover recommendation. |
| `blocks_rollback` | Blocks rollback recommendation. |
| `blocks_ready` | Blocks marking the migration ready. |

An unresolved critical finding is always blocking for cutover and readiness, even if `gate_effect` is incomplete.

## Required Gates

### `can_generate_final_plan`

Returns true only when:

- discovery artifacts exist
- compatibility findings have been produced
- all artifact references used by planning inputs resolve
- human approval for final planning exists
- no unresolved finding has `blocks_plan`

### `can_accept_validation`

Returns true only when:

- validation stage completed
- required validation checks completed for the scenario
- validation result evidence references resolve
- human approval for validation acceptance exists
- no unresolved finding has `blocks_validation_acceptance`

### `can_recommend_cutover`

Returns true only when:

- validation has been accepted
- no unresolved `migration_integrity` finding has `blocks_cutover`
- no unresolved `process_control` finding has `blocks_cutover`
- no unresolved critical `migration_integrity` or `process_control` finding exists
- all cutover recommendation evidence references resolve
- human approval for cutover recommendation exists

Compatibility advisory findings are excluded from this gate.

### `can_recommend_rollback`

Returns true only when:

- rollback criteria exist
- failed or blocked validation evidence exists
- all rollback recommendation evidence references resolve
- human approval for rollback recommendation exists
- no unresolved finding has `blocks_rollback`

### `can_mark_ready`

Returns true only when:

- validation has been accepted
- no unresolved `migration_integrity` finding has `blocks_ready`
- no unresolved `process_control` finding has `blocks_ready`
- no unresolved critical `migration_integrity` or `process_control` finding exists
- all required evidence references resolve
- final runbook has been published
- required human approvals exist

Compatibility advisory findings are reported separately and cannot block readiness for the PostgreSQL-to-PostgreSQL MVP.

## Approval Records

```json
{
  "approval_id": "approval.cutover.workspace_demo.v1",
  "workspace_id": "workspace_demo",
  "scenario_id": "failed_checksum",
  "gate": "cutover_recommendation",
  "actor": "human.reviewer",
  "decision": "approved",
  "created_at": "2026-06-25T12:00:00Z",
  "evidence_refs": ["artifact.validation_report.v1", "artifact.risk_report.v1"],
  "notes": "Approved for demo after reviewing failed checksum evidence."
}
```

Allowed `decision` values are `approved`, `rejected`, and `revoked`.

## Accepted Risk

Accepted-risk decisions may resolve or downgrade a finding only when the finding type allows it. Critical findings require explicit accepted-risk handling and still remain visible in the audit trail.

```json
{
  "decision_id": "accepted_risk.schema.public_orders_missing_fk.v1",
  "finding_key": "schema.missing_constraint:public.orders:orders_customer_id_fkey",
  "actor": "human.reviewer",
  "decision": "accepted_risk",
  "expires_at": "2026-07-25T00:00:00Z",
  "rationale": "Foreign key validation is handled by an upstream contract for this demo scenario.",
  "evidence_refs": ["audit.review.accepted_risk.v1"]
}
```

## Output Shape

```json
{
  "gate": "can_recommend_cutover",
  "allowed": false,
  "blocking_findings": [
    "validation.checksum_mismatch:public.orders:*"
  ],
  "missing_approvals": [
    "cutover_recommendation"
  ],
  "unresolved_evidence_refs": [],
  "checked_at": "2026-06-25T12:00:00Z"
}
```
