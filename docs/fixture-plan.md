# Fixture Plan

The MVP uses Docker-managed PostgreSQL source and target databases. Fixtures should be small, deterministic, and designed to isolate one primary detector wherever possible.

## Databases

| Database | Purpose |
| --- | --- |
| `source-postgres` | Canonical source database. |
| `target-postgres` | Migrated target database with scenario-specific differences. |

Validation tools must connect with read-only roles. Seed scripts may use privileged roles during setup, but runtime validation should not.

## Baseline Schema

The first fixture set should be a small commerce-like schema because it naturally supports row counts, checksums, referential checks, duplicate business keys, and semantic rules.

Suggested tables:

- `customers`
- `orders`
- `order_items`
- `payments`
- `subscriptions`

Suggested business rules:

- order line item totals equal order totals
- payment amounts are non-negative
- active subscriptions reference active customers
- closed orders have a closed timestamp

## Scenario Format

Each scenario should have a JSON or YAML descriptor:

```json
{
  "scenario_id": "failed_checksum",
  "description": "Target row counts and schemas match source, but order content differs.",
  "source_seed": "fixtures/base/source.sql",
  "target_seed": "fixtures/scenarios/failed_checksum/target.sql",
  "critical_tables": ["orders", "payments"],
  "business_keys": {
    "customers": ["email"],
    "orders": ["order_number"]
  },
  "allowed_lag": null,
  "expected_results": "fixtures/scenarios/failed_checksum/expected_findings.json"
}
```

## Required Scenarios

| Scenario | Primary Detector | Expected Primary Finding |
| --- | --- | --- |
| `clean_migration` | Baseline validation | No `migration_integrity` detector findings. |
| `missing_rows` | Row count comparison | `validation.missing_rows`. |
| `schema_drift` | Schema comparison | `schema.type_widened`, `schema.nullability_relaxed`, `schema.unique_constraint_relaxed`, and `schema.extra_target_column`. |
| `schema_relaxed_unique_violation` | Schema-triggered data check | `validation.duplicate_values_after_unique_relaxation`. |
| `bad_types` | Schema comparison | `schema.precision_sensitive_type_change`. |
| `broken_fk` | Referential integrity check | `validation.broken_referential_integrity`. |
| `null_distribution_change` | Null distribution check | `validation.null_distribution_mismatch`. |
| `duplicate_records` | Duplicate business-key check | `validation.duplicate_business_key`. |
| `failed_checksum` | Canonical checksum | `validation.checksum_mismatch`. |
| `unsupported_sql` | Compatibility profile | `compatibility.unsupported_feature_*`. |
| `replication_lag` | Lag-aware row freshness | `validation.replication_lag`. |

## Scenario Rules

- Keep fixtures small enough for full-table comparisons.
- Prefer one intended detector per failure scenario.
- Do not emit `validation.missing_rows` for explained replication lag unless rows are missing beyond the known cutoff.
- The `failed_checksum` scenario is valid only when row counts and schemas match.
- Compatibility advisory findings may appear in clean scenarios, but they must be listed as expected or allowed extras.
- Expected results must use stable `finding_key` values.

## Implemented Directory Layout

```text
fixtures/
  base/
    common.sql
    source.sql
    target.sql
  scenarios/
    clean_migration/
      scenario.json
      expected_findings.json
    failed_checksum/
      target.sql
      scenario.json
      expected_findings.json
    schema_drift/
      target.sql
      scenario.json
      expected_findings.json
    schema_relaxed_unique_violation/
      target.sql
      scenario.json
      expected_findings.json
```

`clean_migration`, `failed_checksum`, `schema_drift`, and `schema_relaxed_unique_violation` are the first implemented scenarios. `schema_drift` proves relaxed schema guarantees stay low when row data remains clean. `schema_relaxed_unique_violation` proves a relaxed unique constraint escalates to a blocking validation finding when duplicate data exists.

## Local Commands

Start the Docker-managed databases:

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

Stop the databases:

```sh
make db-down
```
