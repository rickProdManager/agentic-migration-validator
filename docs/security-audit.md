# Security Audit

Last reviewed: 2026-06-30

## Scope

This audit covers the repository source, public documentation, local dashboard/API surface, Docker fixture configuration, ignored generated outputs, and optional live-model adapter.

The project is a local demo and development tool. It is not currently designed as a multi-user hosted service.

## Summary

No real API keys, access tokens, private keys, or credential files were found in the repository source or public docs.

The audit found several hardening items that were worth fixing before any future public release:

- Docker fixture databases now bind to `127.0.0.1` instead of all interfaces.
- Local API POST routes now reject browser cross-site POST attempts.
- Local API JSON request bodies now have a 64 KiB limit.
- API and static responses now include basic browser security headers.
- Workflow launch failures no longer return raw exception messages.
- Optional live-model endpoint overrides must use HTTPS.
- Generated manifests now prefer repo-relative paths for project-local outputs.
- `.gitignore` now covers common local secret, log, coverage, and database files.

## Reviewed Areas

### Secrets And Local Leakage

Reviewed:

- Source files
- Public docs
- Tests
- Docker Compose
- Local UI assets
- Ignored generated `artifacts/` and `runs/` output

Result:

- No real secrets were found.
- `OPENAI_API_KEY=...` appears only as documentation placeholder text.
- `sk-test` appears only as a unit-test placeholder.
- `AGENTS.md`, `current_status.md`, `artifacts/`, `runs/`, virtualenvs, caches, and local status files are ignored by git.

### Docker Fixtures

Finding:

- Postgres fixture ports were previously declared as `55432:5432` and `55433:5432`, which can bind outside localhost.

Fix:

- Ports now bind as `127.0.0.1:55432:5432` and `127.0.0.1:55433:5432`.

Residual risk:

- Fixture credentials are intentionally static demo credentials. They are acceptable only because the databases are local fixtures and should not be used for real data.

### Local API

Reviewed:

- Static asset serving
- Artifact/evidence file reads
- Workflow run retrieval
- Approval submission
- Workflow launch
- Error responses

Existing protections:

- Static assets are constrained to `ui/`.
- Artifact reads are constrained to `artifacts/` and workflow-run `runs/` stores.
- Workflow run IDs are validated before run-store reads.
- Scenario IDs are validated before workflow execution through the API.

Fixes:

- Added cross-site POST rejection for browser-originated requests.
- Added a 64 KiB JSON body limit.
- Added `X-Content-Type-Options`, `Referrer-Policy`, `Cache-Control`, and a restrictive CSP for HTML.
- Added a visible local-only warning to the served dashboard and API startup output.
- Removed raw exception messages from workflow launch failure responses.

Residual risk:

- The local API is intentionally unauthenticated. It should remain bound to `127.0.0.1` and should not be exposed as a hosted service without adding authentication, authorization, CSRF protection appropriate for hosted use, durable storage controls, and operational logging policy.

### Artifact And Run Stores

Finding:

- Older ignored generated artifacts and runs can contain absolute local paths from earlier executions.

Fix:

- Newly generated project-local artifact and run manifests prefer repo-relative paths.
- `artifacts/` and `runs/` remain ignored because they are reproducible local outputs.

Residual risk:

- Do not force-add generated outputs unless they have been regenerated and reviewed.

### Optional Live Model Adapter

Reviewed:

- Environment variable handling
- API key use
- Endpoint override
- Error handling

Fixes:

- Live model calls remain opt-in.
- Endpoint overrides must use HTTPS.
- HTTP error responses no longer include provider response bodies in raised errors.
- Requests use `"store": false`.

Residual risk:

- A live API key should be provided only through local environment variables or a secret manager. It should never be committed or written to artifact output.

## Pre-Public Checklist

Before making the repository public:

- Run `make test`.
- Run a secret scan over source and docs.
- Confirm `git status --ignored` shows `artifacts/`, `runs/`, `.env*`, `AGENTS.md`, `current_status.md`, caches, and virtualenvs ignored.
- Do not force-add ignored generated outputs.
- Confirm Docker ports remain localhost-bound.
- Confirm README screenshots do not reveal private paths, names, tokens, or browser/account data.
- Keep the README honest that the dashboard/API are local demo surfaces, not hosted production services.

## Verification Commands

Useful local checks:

```sh
make test
make api-smoke
rg -n "OPENAI_API_KEY=|sk-[A-Za-z0-9_-]{32,}|ghp_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|PRIVATE KEY" README.md docs tools scripts tests ui fixtures docker-compose.yml
rg -n "ABSOLUTE_LOCAL_PATH|PRIVATE_WORKSPACE_PATH|COMMIT_ONLY_PLACEHOLDER" README.md docs tools scripts tests ui fixtures docker-compose.yml Makefile pyproject.toml
```
