# Password Vault — Current build status and where to go next

Snapshot of what’s done and what’s left so you can hand work to the agents or continue manually.

---

## Current status summary

| Area | Status | Notes |
|------|--------|--------|
| **Phase 1 (crypto)** | Done | `crypto.py`, `cli.py`; Argon2id + AES-256-GCM; round-trip blob to file. |
| **Phase 2 (DB)** | Done | SQLite schema, migrations, `vault_db.py` (salt, users, folders, entries, attachments); app-level encryption; create_folder, create_entry, get/update/delete entry, get_folders, get_entries, search_entries; recovery key (recovery_salt, wrapped_master_key). |
| **Phase 3 (API)** | Done | Unlock (password, recovery_key, or recovery_answers); lock; folders/entries CRUD; GET /search; GET /generate-password; POST /recovery/setup, POST /recovery/setup-questions, GET /recovery/status, GET /recovery/questions (public); session + audit + config. |
| **Phase 4 (Web UI)** | Done | Login; unlock with password, recovery key, or 3 security questions; mandatory recovery setup after first login (key or 3 questions); lock; folders/entries; view/edit/delete entry; search; generate password; 30s clipboard clear; 15min inactivity. |
| **Agents & rules** | Done | 13 subagents, orchestration, handoffs, api-contract, VOCAB, agent-status, GETTING_STARTED_WITH_AGENTS. |
| **Tests** | Done | `tests/conftest.py`, `test_api.py`, `test_vault_db.py`; 54 tests (unlock with password/key/answers, recovery key and recovery questions setup/status/unlock); run with `pytest tests/` from repo root. |
| **Phase 5 (Docker, backup)** | Deferred | Per your choice; when ready: Dockerfile/compose, then backup to TrueNAS. |

---

## What’s implemented (by layer)

### Backend (`src/vault/`)

- **crypto.py** — Argon2id key derivation, AES-256-GCM encrypt/decrypt, constant-time compare, random bytes.
- **vault_db.py** — Open DB, migrations, salt init, users; create_folder, create_entry, get_entry, update_entry, delete_entry, get_folders, get_entries, search_entries; get_recovery_configured, get_recovery_methods, set_recovery, get_recovery_material, unlock_with_recovery_key; set_recovery_questions, get_recovery_questions, get_qa_recovery_material, unlock_with_recovery_answers.
- **config.py** — `VAULT_DB_PATH`, `VAULT_SESSION_TIMEOUT_MINUTES`, `VAULT_AUDIT_LOG_PATH` from env.
- **audit.py** — `log_event(type, resource_id, user_id)` to file; no secrets.
- **generator.py** — `generate_password(length, upper, lower, digits, symbols)` with `secrets.choice`.
- **api/session.py** — In-memory session store; create/get/delete; timeout by last activity.
- **api/main.py** — POST /unlock (password, recovery_key, or recovery_answers), POST /lock, GET/POST /folders, GET/POST/PATCH/DELETE /entries, GET /search, GET /generate-password; POST /recovery/setup, POST /recovery/setup-questions, GET /recovery/status, GET /recovery/questions (public). Serves `web/index.html` and `/static/`.

### Database

- **migrations/001_initial.sql** — schema_version, vault_meta (salt), users, folders, entries, attachments. Sensitive fields are `*_encrypted` BLOB.
- **migrations/002_recovery_key.sql** — vault_meta.recovery_salt, vault_meta.wrapped_master_key (nullable until recovery set up).
- **migrations/004_recovery_questions.sql** — vault_meta.recovery_qa_salt, recovery_qa_wrapped, recovery_question_1/2/3 (recovery via 3 security questions).

### Web UI (`web/`)

- **index.html** — Login (password, recovery key, or 3 security questions); mandatory recovery setup overlay (key or 3 questions); vault view with Lock, recovery area, search, folders, entries, entry detail, add entry form.
- **app.js** — sessionStorage session; api() with X-Vault-Session; login and unlock with password/key/answers; recovery-required overlay after first login; recovery setup (key or questions form); loadRecoveryStatus; folders/entries CRUD; search; generate password; 30s clipboard clear; 15min inactivity.

### Docs and tooling

- Design: DESIGN_AND_EDUCATION.md, PASSWORD_VAULT_QUESTIONS.md.
- User guide: HOW_IT_WORKS.md.
- Code walkthrough: EDUCATIONAL_CODE_WALKTHROUGH.md.
- Deploy: DEPLOY_DOCKER_NGINX.md.
- Agents: AGENTS_AND_RULES_DESIGN.md, docs/GETTING_STARTED_WITH_AGENTS.md, docs/handoffs/README.md, docs/agent-status.md, docs/api-contract.md, VOCAB.md.
- Tests: tests/README.md, conftest.py, test_api.py, test_vault_db.py; run `pytest tests/` from repo root.

---

## What's missing (where to go next)

Remaining work in rough priority order:

### 1. UI polish (optional)

- Clearer layout, labels, and flows; improve discoverability. You mentioned the UI felt basic—can be done incrementally.

### 2. Attachments (optional, later)

- **Backend:** POST/GET/DELETE for attachment blobs per entry; vault_db already has `attachments` table; add API and encryption of blob.
- **Frontend:** Upload/list/delete attachments on entry detail.
- Defer until you want file storage per entry.

### 3. Phase 5 (Docker, backup to TrueNAS)

- **Docker:** Dockerfile (or compose) for the app; port 8001; volume for vault DB and audit log; env for config.
- **Backup:** Job (cron or sidecar) that exports encrypted backup (e.g. copy vault.db + encrypt or use app export) and pushes to TrueNAS (SMB/NFS/rclone).
- When ready, break into agent-sized tasks; see DEPLOY_DOCKER_NGINX.md.

### 4. Web extensions / mobile (later)

- Browser extensions (Windows/Linux/iOS) and mobile autofill (Android/iOS) for filling credentials on sites/apps. Depends on your target platforms.

---

## Suggested order to continue

1. **UI polish** — Incremental improvements to layout and UX when you want a friendlier interface.
2. **Attachments** — When you need file storage per entry; backend + frontend trios.
3. **Phase 5** — Docker then backup to TrueNAS when you're ready to deploy.
4. **Extensions / mobile** — When you want autofill outside the web app.

Use **docs/GETTING_STARTED_WITH_AGENTS.md** to hand work to the main Agent (with "Proceed?" and git commit prompts as you configured).

---

## Quick reference

- **Run app:** From repo root with venv: `VAULT_DB_PATH=demo_vault.db uvicorn vault.api.main:app --host 127.0.0.1 --port 8001` → http://127.0.0.1:8001/
- **Init DB (no vault yet):** Run `python scripts/phase2_demo.py` once to create salt, user, folder, and sample entry.
- **API contract:** docs/api-contract.md.
- **Agent workflow:** docs/GETTING_STARTED_WITH_AGENTS.md; orchestration in .cursor/rules/orchestration.mdc.
