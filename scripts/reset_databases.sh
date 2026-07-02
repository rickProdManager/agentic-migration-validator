#!/usr/bin/env sh
set -eu

SCENARIO="${1:-clean_migration}"
SOURCE_SEED="/fixtures/base/source.sql"
QUIET="${QUIET:-0}"

case "$SCENARIO" in
  clean_migration)
    TARGET_SEED="/fixtures/base/target.sql"
    ;;
  broken_fk)
    TARGET_SEED="/fixtures/scenarios/broken_fk/target.sql"
    ;;
  failed_checksum)
    TARGET_SEED="/fixtures/scenarios/failed_checksum/target.sql"
    ;;
  missing_rows)
    TARGET_SEED="/fixtures/scenarios/missing_rows/target.sql"
    ;;
  replication_lag)
    TARGET_SEED="/fixtures/scenarios/replication_lag/target.sql"
    ;;
  schema_drift)
    TARGET_SEED="/fixtures/scenarios/schema_drift/target.sql"
    ;;
  schema_relaxed_unique_violation)
    TARGET_SEED="/fixtures/scenarios/schema_relaxed_unique_violation/target.sql"
    ;;
  *)
    echo "Unknown scenario: $SCENARIO" >&2
    echo "Known scenarios: broken_fk, clean_migration, failed_checksum, missing_rows, replication_lag, schema_drift, schema_relaxed_unique_violation" >&2
    exit 2
    ;;
esac

wait_for_postgres() {
  service="$1"
  attempts=0

  until docker compose exec -T "$service" pg_isready -U validator_admin -d migration_validator >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 30 ]; then
      echo "Timed out waiting for $service" >&2
      exit 1
    fi
    sleep 1
  done
}

run_seed() {
  service="$1"
  seed="$2"

  if [ "$QUIET" = "1" ]; then
    quiet_flag="-q"
  else
    quiet_flag=""
  fi

  docker compose exec -T "$service" psql $quiet_flag \
    -v ON_ERROR_STOP=1 \
    -U validator_admin \
    -d migration_validator \
    -f "$seed"
}

if [ "$QUIET" = "1" ]; then
  docker compose up -d source-postgres target-postgres >/dev/null
else
  docker compose up -d source-postgres target-postgres
fi
wait_for_postgres source-postgres
wait_for_postgres target-postgres

run_seed source-postgres "$SOURCE_SEED"
run_seed target-postgres "$TARGET_SEED"

if [ "$QUIET" != "1" ]; then
  echo "Loaded scenario '$SCENARIO'"
fi
