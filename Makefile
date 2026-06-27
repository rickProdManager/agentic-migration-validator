.PHONY: test db-up db-reset db-down db-logs validate-scenario

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
SCENARIO ?= clean_migration

test:
	$(PYTHON) -B -m pytest -q -p no:cacheprovider

db-up:
	docker compose up -d source-postgres target-postgres

db-reset:
	sh scripts/reset_databases.sh $(SCENARIO)

validate-scenario:
	@QUIET=1 sh scripts/reset_databases.sh $(SCENARIO) >/dev/null 2>&1
	@$(PYTHON) -B scripts/validate_scenario.py $(SCENARIO)

db-down:
	docker compose down

db-logs:
	docker compose logs -f source-postgres target-postgres
