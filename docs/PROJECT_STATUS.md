# Password Vault — Current build status and where to go next

Snapshot of what’s done and what’s left so you can hand work to the agents or continue manually.

---

## Current status summary

| Area | Status | Notes |
|------|--------|--------|
| **Phase 1 (crypto)** | Done | `crypto.py`, `cli.py`; Argon2id + AES-256-GCM; round-trip blob to file. |
| **Phase 2 (DB)** | Done | SQLite schema, migrations, `vault_db.py` (salt, users, folders, entries, attachments); app-level encryption; `create_folder`, `create_entry`, `get_folders`, `get_entries`. |
| **Phase 3 (API)** | Mostly done | Unlock, lock, GET folders, GET entries, POST entry, generate-password; session + audit + config. **Missing:** POST folder, edit/delete entry, search. |
| **Phase 4 (Web UI)** | Mostly done | Login, lock, list folders/entries, view entry, add entry, generate password, 30s clipboard clear, 15min inactivity. **Missing:** Create folder, edit/delete entry, search. |
| **Agents & rules** | Done | 13 subagents, orchestration, handoffs, api-contract, VOCAB, agent-status, GETTING_STARTED_WITH_AGENTS. |
| **Tests** | Not started | `tests/` has README only; no pytest tests yet. |
| **Phase 5 (Docker, backup)** | Deferred | Per your choice; after app features. |

---

## What’s implemented (by layer)

### Backend (`src/vault/`)

- **crypto.py** — Argon2id key derivation, AES-256-GCM encrypt/decrypt, constant-time compare, random bytes.
- **vault_db.py** — Open DB, migrations, salt init, users, **create_folder**, **create_entry**, get_folders, get_entries. No update/delete entry or search yet.
- **config.py** — `VAULT_DB_PATH`, `VAULT_SESSION_TIMEOUT_MINUTES`, `VAULT_AUDIT_LOG_PATH` from env.
- **audit.py** — `log_event(type, resource_id, user_id)` to file; no secrets.
- **generator.py** — `generate_password(length, upper, lower, digits, symbols)` with `secrets.choice`.
- **api/session.py** — In-memory session store; create/get/delete; timeout by last activity.
- **api/main.py** — Routes: POST /unlock, POST /lock, GET /folders, GET /entries (requires `folder_id`), POST /entries, GET /generate-password. Serves `web/index.html` and `/static/`. **No** POST /folders, no PATCH/DELETE for entries, no search.

### Database

- **migrations/001_initial.sql** — schema_version, vault_meta (salt), users, folders, entries, attachments. Sensitive fields are `*_encrypted` BLOB. No recovery-key or other new tables.

### Web UI (`web/`)

- **index.html** — Login form, vault view with folder list, entry list, entry detail, “Add entry” form, Lock. No “Create folder” or edit/delete entry UI.
- **app.js** — sessionStorage session; `api()` with X-Vault-Session; login, lock, load folders/entries, show entry detail, add entry, generate password, 30s clipboard clear, 15min inactivity. No create-folder, edit, delete, or search.

### Docs and tooling

- Design: DESIGN_AND_EDUCATION.md, PASSWORD_VAULT_QUESTIONS.md.
- User guide: HOW_IT_WORKS.md.
- Code walkthrough: EDUCATIONAL_CODE_WALKTHROUGH.md.
- Deploy: DEPLOY_DOCKER_NGINX.md.
- Agents: AGENTS_AND_RULES_DESIGN.md, docs/GETTING_STARTED_WITH_AGENTS.md, docs/handoffs/README.md, docs/agent-status.md, docs/api-contract.md, VOCAB.md.
- Test layout: tests/README.md (pytest from repo root); no test files yet.

---

## What’s missing (where to go next)

In order that fits your design and agent workflow:

### 1. Create folder (API + UI)

- **Backend:** Add **POST /folders** (body e.g. `{ "name": string }`), call `vault_db.create_folder`, audit, return `{ "id": number }`. Contract already in design; `vault_db.create_folder` exists.
- **Frontend:** “Create folder” control (e.g. button + name input), call POST /folders, refresh folder list.
- **Good first agent task:** Frontend trio then backend trio (or backend then frontend). Update docs/api-contract.md and HOW_IT_WORKS.md.

### 2. Edit entry (API + UI)

- **Backend:** **PATCH or PUT /entries/{id}** (body: optional title, username, password, notes, url); load entry, validate ownership/folder, update in vault_db (new `update_entry`), audit.
- **Database:** Add `update_entry` in vault_db (update encrypted fields by id).
- **Frontend:** Edit button on entry detail; form or inline edit; save calls PATCH/PUT.
- **Agent flow:** Backend trio (plan → implement → test) then frontend trio; update api-contract and HOW_IT_WORKS.

### 3. Delete entry (API + UI)

- **Backend:** **DELETE /entries/{id}**; vault_db `delete_entry(id)`; audit.
- **Database:** Add `delete_entry` in vault_db.
- **Frontend:** Delete button with confirm; call DELETE then refresh list.
- Can be done with edit in one go (backend + frontend trios for “edit and delete entry”).

### 4. Search (API + UI)

- **Backend:** **GET /entries?q=...** (or /search) that searches across decrypted title, username, notes, url (and optionally password for “show in list” policy). Requires scanning entries per folder (or per user) and decrypting; keep it simple (e.g. filter in app, no full-text index for now).
- **Frontend:** Search box; call search API; show results (e.g. entries list).
- **Agent flow:** Backend trio then frontend trio; add to api-contract and HOW_IT_WORKS.

### 5. Recovery key (backend + DB + minimal UI)

- **Design:** Recovery key generated once, shown once, stored offline; used to unlock if master password is lost (e.g. derive key from recovery key, store wrapped key in vault header).
- **Database:** Migration for recovery-key storage (e.g. wrapped key or recovery-key hash in vault_meta); no plaintext recovery key in DB.
- **Backend:** Generate and store wrapped key at setup; unlock endpoint accepts either password or recovery key; audit for recovery unlock.
- **Frontend:** Minimal UI: “Set up recovery key” (show once, copy/save), “Unlock with recovery key” (optional flow).
- **Agent flow:** Cross-domain: backend trio, database trio, frontend trio, then integration-reviewer; update api-contract, HOW_IT_WORKS, VOCAB.

### 6. Attachments (optional, later)

- **Backend:** POST/GET/DELETE for attachment blobs per entry; vault_db already has `attachments` table; add API and encryption of blob.
- **Frontend:** Upload/list/delete attachments on entry detail.
- Can be deferred until after recovery key and search.

### 7. Tests

- **Layout:** `tests/` with e.g. `test_api.py`, `test_vault_db.py`; run with `pytest tests/` from repo root (venv).
- **Scope:** Unlock, lock, list folders, list entries, create entry, create folder (once added), optional edit/delete; use test DB (e.g. temp file or `vault_test.db`). No secrets in test output.
- **Agent:** backend-tester and database-tester can add and run tests; standard is in tests/README.md.

### 8. Phase 5 (Docker, backup to TrueNAS)

- **Docker:** Dockerfile (or compose) for the app; port 8001; volume for vault DB and audit log; env for config.
- **Backup:** Job (cron or sidecar) that exports encrypted backup (e.g. copy vault.db + encrypt or use app export) and pushes to TrueNAS (SMB/NFS/rclone).
- Deferred until app features above are in place; then can be broken into agent-sized tasks.

---

## Suggested order to continue

1. **Create folder** — Small, clear scope; backend already has `create_folder`; add POST /folders and UI. Use agents: “Add Create folder feature (API + UI); frontend trio then backend trio, follow orchestration rules.”
2. **Edit + delete entry** — Backend: update_entry, delete_entry, PATCH/DELETE routes; frontend: edit/delete on entry. One or two agent runs (backend trio + frontend trio).
3. **Search** — Backend search endpoint; frontend search box. Backend trio then frontend trio.
4. **Recovery key** — Cross-domain; backend + DB + minimal UI; then integration-reviewer.
5. **Tests** — Add pytest under `tests/` for API and vault_db; backend-tester/database-tester can own this.
6. **Phase 5** — When you’re ready; Docker then backup.

Use **docs/GETTING_STARTED_WITH_AGENTS.md** to hand each of these to the main Agent (with “Proceed?” and git commit prompts as you configured).

---

## Quick reference

- **Run app:** From repo root with venv: `VAULT_DB_PATH=demo_vault.db uvicorn vault.api.main:app --host 127.0.0.1 --port 8001` → http://127.0.0.1:8001/
- **Init DB (no vault yet):** Run `python scripts/phase2_demo.py` once to create salt, user, folder, and sample entry.
- **API contract:** docs/api-contract.md.
- **Agent workflow:** docs/GETTING_STARTED_WITH_AGENTS.md; orchestration in .cursor/rules/orchestration.mdc.
