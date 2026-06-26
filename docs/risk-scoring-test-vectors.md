# Risk Scoring Test Vectors

These vectors bridge the PRD risk rubric to implementation. They should become the first assertions in `risk_scoring.py` before the broader fixture evals are wired up.

## Scoring Decisions

The per-finding cap applies after multiplier and instance bonus:

```text
risk_points = round_half_up(min(base_points * blast_radius_multiplier + instance_bonus, per_finding_cap))
```

This means the instance bonus can be absorbed at the highest blast-radius tier when `base_points * 2.0` already equals the `2x base_points` cap. That is deliberate. The cap prevents one finding from running away; true escalation should happen through severity or `derived_risk_factor` records.

Process-control records must carry severity because axis floors are severity-derived:

| Gate Finding | Severity | Base Points |
| --- | --- | ---: |
| Missing required human approval | `moderate` | 10 |
| Runbook missing rollback criteria | `high` | 20 |
| Unresolved evidence reference | `high` | 25 |
| Qualitative reviewer critique | `low` to `high` | 0-10 |

Detector records also carry severity in the PRD base-points table. The test vectors assume those severities are loaded from the rubric, not inferred from points.

The 2.0 blast-radius tier escalates unresolved high-severity `migration_integrity` validation findings to `critical`. This is why the five-table missing-rows vector expects Critical even though no individual table is marked as critical path.

Compatibility advisory findings must not carry readiness-blocking gate effects such as `blocks_cutover` or `blocks_ready`. Cutover readiness reads `migration_integrity` plus process gates, not `compatibility_advisory`.

Severity floors:

| Severity | Floor |
| --- | ---: |
| `info` | 0 |
| `low` | 0 |
| `moderate` | 25 |
| `high` | 50 |
| `critical` | 75 |

Axis bands:

| Score | Band |
| --- | --- |
| 0-24 | Low |
| 25-49 | Moderate |
| 50-74 | High |
| 75-100 | Critical |

## Per-Finding Vectors

| ID | Input | Calculation | Expected Risk Points | Expected Severity | Expected Axis Band |
| --- | --- | --- | ---: | --- | --- |
| `round_half_up_checksum` | `validation.checksum_mismatch`, base 35, multiplier 1.5, bonus 0, cap 70 | `round_half_up(min(35 * 1.5 + 0, 70))` | 53 | `high` | High |
| `multiplier_1_0` | `validation.null_distribution_mismatch`, base 12, multiplier 1.0, bonus 0, cap 24 | `round_half_up(min(12 * 1.0 + 0, 24))` | 12 | `moderate` | Moderate |
| `multiplier_1_25` | `validation.duplicate_business_key`, base 20, multiplier 1.25, bonus 0, cap 40 | `round_half_up(min(20 * 1.25 + 0, 40))` | 25 | `high` | High |
| `multiplier_1_5` | `schema.missing_primary_key`, base 25, multiplier 1.5, bonus 0, cap 50 | `round_half_up(min(25 * 1.5 + 0, 50))` | 38 | `high` | High |
| `five_table_missing_rows_cap` | `validation.missing_rows`, base 30, multiplier 2.0, bonus 8 for five affected tables, cap 60 | `round_half_up(min(30 * 2.0 + 8, 60))` | 60 | `critical` | Critical |
| `bonus_survives_below_cap` | `schema.missing_constraint`, base 15, multiplier 1.25, bonus 4, cap 30 | `round_half_up(min(15 * 1.25 + 4, 30))` | 23 | `moderate` | Moderate |

## Axis Vectors

| ID | Inputs | Expected Axis Scores | Expected Bands | Notes |
| --- | --- | --- | --- | --- |
| `clean_integrity` | No `migration_integrity` findings | `migration_integrity: 0` | `migration_integrity: Low` | Clean migration must stay Low on integrity. |
| `clean_with_advisory` | No `migration_integrity` findings; one `compatibility_advisory` finding with base 8, severity `low` | `migration_integrity: 0`, `compatibility_advisory: 8` | `migration_integrity: Low`, `compatibility_advisory: Low` | Warehouse advisory risk must not pollute integrity risk. |
| `process_missing_approval` | One `gate.required_approval_missing`, base 10, severity `moderate` | `process_control: 25` | `process_control: Moderate` | Severity floor dominates the 10-point raw score. |
| `process_unresolved_evidence` | One `artifact.unresolved_evidence_reference`, base 25, severity `high` | `process_control: 50` | `process_control: High` | High severity sets the process floor. |
| `critical_single_blast_radius` | One `validation.missing_rows`, base 30, multiplier 2.0, severity `critical` | `migration_integrity: 75` minimum, risk points 60 | `migration_integrity: Critical` | Critical severity floor dominates the 60-point raw score. |
| `critical_compounding_highs` | Two unresolved high-severity validation findings plus `risk.derived.compounding_high_validation_failures`, severity `critical`, base 0 | `migration_integrity: 75` minimum | `migration_integrity: Critical` | Derived factor sets severity floor without duplicating detector points. |
| `advisory_never_blocks_cutover` | One `compatibility_advisory` finding with base 20, severity `moderate`, and no blocking `gate_effect` | `compatibility_advisory: 25`; `migration_integrity: 0` | `compatibility_advisory: Moderate`; `migration_integrity: Low` | Advisory findings may raise advisory risk but must not block cutover readiness. |

## Implementation Notes

- Use decimal `ROUND_HALF_UP`; do not use Python's built-in `round()`.
- Treat `round_half_up_checksum` as the load-bearing rounding canary. The `multiplier_1_5` vector also lands on `.5`, but `37.5 -> 38` passes under both half-up and banker's rounding because 38 is even.
- Compute detector findings first, then apply derived risk factors.
- Derived escalation replaces or annotates existing findings; it does not add duplicate detector scores.
- Compute `migration_integrity`, `compatibility_advisory`, and `process_control` separately.
- Cutover readiness reads `migration_integrity` plus process gates. It does not read `compatibility_advisory`.
