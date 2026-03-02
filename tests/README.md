# Tests

Standard test layout for the password vault project. All tests use a **temporary DB and audit log** (see `conftest.py`); production data is never touched.

## Run tests

From the repo root, with the project venv activated:

```bash
pytest tests/
```

Or with verbose output: `pytest tests/ -v`

## What’s included

- **conftest.py** — Sets `VAULT_DB_PATH` and `VAULT_AUDIT_LOG_PATH` to a temp dir before importing the app. Fixtures: `client`, `initialized_vault` (DB with salt + user), `session_headers` (unlock once, return `X-Vault-Session` headers).
- **test_api.py** — API tests: unlock (422/400/200), lock (204), GET/POST folders (401, 422, 200, create and list), GET/POST entries (401, 422, 200, full create-folder-and-entry flow), generate-password (401, 200, length). No secrets in response assertions.
- **test_vault_db.py** — DB layer: migrations and schema_version, init_salt/get_salt, create_folder and get_folders (decrypted name), create_entry and get_entries (decrypted fields).

Backend-tester and database-tester subagents run `pytest tests/` from repo root with venv. Add tests here as the project grows.
