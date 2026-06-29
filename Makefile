.PHONY: test api-smoke db-up db-reset db-down db-logs validate-scenario schema-diff enforce-gate draft-runbook run-api run-workflow write-artifacts eval-scenarios

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
SCENARIO ?= clean_migration
GATE ?= can_mark_ready
API_BASE_URL ?= http://127.0.0.1:8080
SMOKE_WORKFLOW_SCENARIO ?=

test:
	$(PYTHON) -B -m pytest -q -p no:cacheprovider

api-smoke:
	@$(PYTHON) -B scripts/smoke_api.py --base-url $(API_BASE_URL) $(if $(SMOKE_WORKFLOW_SCENARIO),--workflow-scenario $(SMOKE_WORKFLOW_SCENARIO),)

db-up:
	docker compose up -d source-postgres target-postgres

db-reset:
	sh scripts/reset_databases.sh $(SCENARIO)

validate-scenario:
	@QUIET=1 sh scripts/reset_databases.sh $(SCENARIO) >/dev/null 2>&1
	@$(PYTHON) -B scripts/validate_scenario.py $(SCENARIO)

schema-diff:
	@$(PYTHON) -B scripts/diff_schema.py $(SCENARIO)

enforce-gate:
	@$(PYTHON) -B scripts/enforce_gate.py $(SCENARIO) $(GATE)

draft-runbook:
	@$(PYTHON) -B scripts/generate_runbook.py $(SCENARIO)

write-artifacts:
	@$(PYTHON) -B scripts/write_artifacts.py

run-workflow:
	@$(PYTHON) -B scripts/run_workflow.py

run-api:
	@$(PYTHON) -B scripts/serve_api.py

eval-scenarios:
	@$(PYTHON) -B scripts/run_eval.py

db-down:
	docker compose down

db-logs:
	docker compose logs -f source-postgres target-postgres
