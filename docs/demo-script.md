# Demo Script

Use this as a short walkthrough for interviews, portfolio reviews, or cold-reader validation.

## Setup

In one terminal:

```sh
make db-up
make run-api
```

Open `http://127.0.0.1:8080/`.

The dashboard is local and dependency-free. It uses Docker PostgreSQL fixtures, the stdlib JSON API, and ignored local `runs/` and `artifacts/` output.

## Talk Track

Agentic Migration Validator is a migration-readiness workflow where model-backed advisors can explain and draft runbooks, but deterministic checks own facts and gates.

The key safety boundary is that advisors propose, deterministic invariants dispose. If a checksum mismatch, schema-triggered data violation, unresolved evidence reference, or missing approval blocks readiness, the UI can explain it and record human inputs, but it cannot edit the gate result directly.

Lead with the row-gap contrast, because it explains the architecture faster than a feature tour:

- `Missing Rows` and `Replication Lag` use the same missing target payment row.
- `Missing Rows` blocks readiness because the row loss is unexplained.
- `Replication Lag` stays non-blocking because a declared source freshness cutoff explains the gap.

That is the thesis in one example: the system is not asking an LLM whether the migration feels safe. Deterministic evidence and policy make the cutover decision; advisor prose is allowed only behind that boundary.

## Dashboard Walkthrough

1. Start with the `New Run` panel.
2. Select `Missing Rows`.
3. Run the workflow.
4. Point out that the newly persisted run is selected automatically.
5. In `Run Result`, show the completed workflow summary.
6. In `Workflow Progress`, show the deterministic stages:
   - Run Deterministic Evaluations
   - Generate Runbook Drafts
   - Validate Artifact Bundle
   - Write Artifact Bundle
7. In `Stage Transitions`, show that stage movement is explicitly checked.
8. In `Readiness Gates`, show that readiness is blocked by the deterministic missing-row finding.
9. Run `Replication Lag` and point out that it uses the same missing target row but stays non-blocking because policy evidence explains the gap.
10. In `Run Artifacts`, open the runbook draft.
11. In `Evidence Reference`, show that runbook claims resolve back to artifact/evidence entries.
12. In `Approval Action`, submit a validation approval.
13. In `Audit Trail`, show that the approval was appended as an audit event.

The important point: approval submission changes persisted inputs and audit state. It does not directly edit readiness gates. Gates recompute from findings plus approval state.

## Scenario Contrast

Use these scenarios to explain why this is more than a checksum demo:

| Scenario | What To Show | Meaning |
| --- | --- | --- |
| `Broken Foreign Key` | Target drops a foreign key and has an order pointing at a missing customer. | Referential drift becomes blocking when row data contains orphaned references. |
| `Missing Rows` | Target is missing a source payment row with no lag policy. | Unexplained row loss blocks cutover/readiness. |
| `Replication Lag` | The same target gap is explained by a source freshness cutoff. | Known lag is surfaced without pretending data was lost. |
| `Schema Drift` | Dropped uniqueness exists, but row data still has unique payment references. | Structural drift is noted, but migration integrity is not blocked. |
| `Relaxed Unique Violation` | The same dropped uniqueness exists, and row data now has duplicate payment references. | The triggered data check escalates the issue into a blocking migration-integrity finding. |

This demonstrates the two-step logic:

1. Catalog metadata identifies where the migration needs scrutiny.
2. Row data determines whether the difference actually breaks migration integrity.

## CLI Backup

If the dashboard is not available, the same thesis is visible from the command line:

```sh
make eval-scenarios
```

Then compare:

- `broken_fk`: dropped foreign key plus orphaned row, gates blocked.
- `clean_migration`: no findings, gates allowed.
- `failed_checksum`: checksum finding, gates blocked.
- `missing_rows`: missing-row finding, gates blocked.
- `replication_lag`: lag finding, gates allowed.
- `schema_drift`: schema findings, triggered data checks pass, gates allowed.
- `schema_relaxed_unique_violation`: schema relaxation plus duplicate data, gates blocked.

To prove gates are enforced as a hard stop:

```sh
make enforce-gate SCENARIO=missing_rows GATE=can_mark_ready
```

That command exits nonzero because deterministic readiness is blocked. Then run:

```sh
make enforce-gate SCENARIO=replication_lag GATE=can_mark_ready
```

That command exits successfully because the same row gap is explained by the scenario's freshness policy.

## Closing Line

This project is not trying to make an advisor sound confident. It builds the deterministic substrate that keeps an advisor honest: typed findings, evidence references, audit events, approvals, and gates that the prose cannot bypass.
