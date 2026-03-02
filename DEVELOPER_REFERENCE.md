# Developer reference

API contract, project status, Big-O and operations, production readiness, test run report, and glossary. For the full doc index see [DOCS.md](DOCS.md).

---

## Table of contents

1. [API contract](#1-api-contract)
2. [Project status](#2-project-status)
3. [Big-O and operations](#3-big-o-and-operations)
4. [Production readiness](#4-production-readiness)
5. [Test run report](#5-test-run-report)
6. [Glossary (VOCAB)](#6-glossary-vocab)

---

## 1. API contract

Short contract so frontend and backend stay aligned. Update when adding or changing endpoints.

### Current endpoints

- **GET /health** — No auth. 200 `{ "status": "ok" }`. Liveness.
- **GET /ready** — No auth. 200 `{ "status": "ready" }` if DB reachable, 503 otherwise. Readiness.
- **GET /vault/status** — No auth. `{ "initialized": boolean }`. First-time setup vs unlock form.
- **POST /setup** — Body: `{ "username", "password" }`. First-time only: creates first user; returns `{ "session_id" }`. 400 if already initialized.
- **POST /signup** — Body: `{ "username", "password" }`. Creates new user when vault initialized. 400 if not initialized or username taken.
- **POST /vault/reset** — Body: `{ "username", "password" }`. Verifies that user, then deletes DB. 401 if wrong credentials.
- **POST /unlock** — Body: `{ "username" }` plus exactly one of `{ "password" }`, `{ "recovery_key" }`, or `{ "recovery_answers": [ string, string, string ] }`. Returns `{ "session_id" }`. 400 if invalid; 429 if rate limited.
- **POST /lock** — Header: `X-Vault-Session`. 204 No Content.
- **GET /folders** — Header: `X-Vault-Session`. List of `{ "id", "name" }`.
- **GET /entries** — Header: `X-Vault-Session`. Query: `folder_id` (optional). List of entries.
- **POST /entries** — Header: `X-Vault-Session`. Body: `{ "folder_id", "title", "username", "password", "notes", "url" }`. Returns `{ "id" }`.
- **PATCH /entries/{entry_id}** — Header: `X-Vault-Session`. Body: optional fields to update. 204. 404 if not found or not owned.
- **DELETE /entries/{entry_id}** — Header: `X-Vault-Session`. 204. 404 if not found or not owned.
- **GET /search** — Header: `X-Vault-Session`. Query: `q`. Searches title, username, notes, URL. Returns list of entries with folder_id, folder_name.
- **POST /recovery/setup** — Header: `X-Vault-Session`. Returns `{ "recovery_key" }` (show once).
- **POST /recovery/setup-questions** — Header: `X-Vault-Session`. Body: `{ "question_1", "question_2", "question_3", "answer_1", "answer_2", "answer_3" }`. 204.
- **GET /recovery/status** — Header: `X-Vault-Session`. Returns `{ "configured", "key_configured", "questions_configured", "questions" }`.
- **GET /recovery/questions** — No auth. Query: `username` (required). Returns `{ "questions_configured", "questions" }`. Rate limited (429) to prevent username enumeration.
- **GET /generate-password** — Query: `length`, `upper`, `lower`, `digits`, `symbols`. Returns `{ "password" }`. Session required.

401 on missing or invalid session.

---

## 2. Project status

Snapshot of what’s done and where to go next.

### Current status summary

| Area | Status | Notes |
|------|--------|--------|
| **Phase 1 (crypto)** | Done | crypto.py, cli.py; Argon2id + AES-256-GCM. |
| **Phase 2 (DB)** | Done | SQLite, migrations, vault_db.py; app-level encryption; recovery key; multi-user. |
| **Phase 3 (API)** | Done | Unlock (password/recovery key/answers), lock, CRUD, search, generate-password, recovery endpoints; session, audit, config. |
| **Phase 4 (Web UI)** | Done | Login, signup, recovery setup/unlock, folders/entries, search, generate, 30s clipboard, 15min inactivity. |
| **Agents & rules** | Done | 13 subagents, orchestration, handoffs, api-contract, VOCAB, agent-status. |
| **Tests** | Done | pytest; 58 tests (API + DB). Run: `pytest tests/` from repo root. |
| **Phase 5 (Docker, backup)** | Deferred | Dockerfile/compose; backup to TrueNAS when ready. |

### What’s missing (where to go next)

1. **UI polish (optional)** — Clearer layout, labels, flows.
2. **Attachments (optional)** — POST/GET/DELETE for attachment blobs; vault_db has attachments table; add API and encryption.
3. **Phase 5** — Docker + backup job to TrueNAS (see [Deploy and operations](DEPLOY_AND_OPERATIONS.md)).
4. **Web extensions / mobile (later)** — Browser extensions and mobile autofill.

### Quick reference

- **Run app:** From repo root with venv: `VAULT_DB_PATH=demo_vault.db uvicorn vault.api.main:app --host 127.0.0.1 --port 8001` → http://127.0.0.1:8001/
- **Init DB (no vault yet):** Run `python scripts/phase2_demo.py` once.
- **API contract:** This document, section 1.
- **Agent workflow:** [Agents and workflow](AGENTS_AND_WORKFLOW.md).

---

## 3. Big-O and operations

### Big-O complexity

*F = folders per user, E = entries per folder, N = total entries per user, S = active sessions.*

**Session store:** get/create/delete O(1); store size O(S).

**Database:** get_user_by_username O(1); get_folders O(F); get_entries O(E); get_entry O(1); create/update/delete O(1); **search_entries O(N)** (scans user entries; no index on encrypted content).

**Crypto:** derive_key O(1) in input length (Argon2id cost fixed); encrypt/decrypt O(n) in blob size.

**Per-request:** Unlock/setup/signup O(1); list folders O(F); list entries O(E); get one entry O(1); search O(N); create folder/entry O(1).

### SQL injection

**Mitigated.** vault_db.py uses **parameterized queries** only (? placeholders, tuple parameters). No string formatting or concatenation of user input in SQL.

### Input validation

**API:** Pydantic models with min_length and max_length: username 64, title 256, notes 4096, url 2048, recovery q/a 256 each. Business rules in handlers with HTTPException (400, 401, 404).

**Frontend:** required, trim, escapeHtml, safeUrlForHref (only http/https in links).

### Logging strategy

- **Audit log:** audit.log_event(type, resource_id, user_id) to file; no secrets.
- **Application logging:** Python `logging` to stdout; level from VAULT_LOG_LEVEL (optional).
- **No secrets** in any log.

### Error tracking

Optional Sentry (VAULT_SENTRY_DSN); server-side redaction of secrets before send.

### Monitoring

- **Health:** GET /health, GET /ready for liveness/readiness.
- No in-app metrics (Prometheus) or APM; use health endpoints and external monitoring as needed.

---

## 4. Production readiness

### What’s in place

Auth & crypto, SQL injection mitigation, input validation (including max_length on strings), no secrets in code/logs, audit trail (including user_id on lock), tests, Docker deployment, config from env, pinned dependencies, health/ready endpoints, optional Sentry, rate limiting on auth and recovery/questions, optional session persistence, config validation on startup, backup/restore docs, dependency scanning docs, CORS middleware. DB connection context manager (DRY). Recovery key generation in vault_db. Reset handles os.remove failure (500 on error). Session persistence catches specific exceptions only.

### What was added (recommendations implemented)

- HTTPS at reverse proxy (documented).
- Health and readiness endpoints.
- Graceful shutdown (Uvicorn default; documented).
- Application logging (configurable level).
- Optional error tracking (Sentry with redaction).
- Rate limiting on auth endpoints.
- Optional SQLite-backed encrypted session persistence.
- Config validation on startup (paths, timeouts, session store, rate limit).
- Backup and restore procedures (see [Deploy and operations](DEPLOY_AND_OPERATIONS.md#3-backup-and-restore)).
- Dependency scanning (pip-audit; see [Deploy and operations](DEPLOY_AND_OPERATIONS.md#4-dependency-scanning)).
- CORS (configurable origins).

### Verdict

For homelab/family use the app is **usable and secure**. For stricter production: use HTTPS at the proxy, health/ready, backup/restore, config validation, and optional logging and error tracking as already implemented.

### Beyond homelab (2025-02-03)

Hardening for potential use beyond homelab: DB connection context manager (DRY), max_length on all string fields, rate limit on GET /recovery/questions, lock audit includes user_id, reset returns 500 on os.remove failure, session persistence catches specific exceptions only, clipboard API guard in frontend, no external quote API dependency, shared submitAuthForm for setup/signup.

---

## 5. Test run report

**Date:** 2025-02-03. **Scope:** Backend, database, frontend, security.

- **Backend (API):** 46 tests passed. Vault status, setup, signup, reset, unlock (password/recovery key/answers), lock, recovery, folders, entries, search, generate-password.
- **Database:** 10 tests passed. Migrations, init, CRUD, search, per-user recovery.
- **Full pytest:** 58 tests passed.
- **Frontend:** Code review; API consistency; no secrets in DOM/console; XSS mitigation (escapeHtml, safeUrlForHref). No E2E framework in repo.
- **Security audit:** Auth/crypto OK; parameterized SQL; validation present; no secrets in logs; URL scheme restricted for links.

**Verdict:** PASS. One XSS vector (URL in href) was fixed with safeUrlForHref.

---

## 6. Glossary (VOCAB)

Terms used in the user guide and project.

- **Session** — Period after you unlock the vault; you stay logged in until lock, close tab, or inactivity timeout.
- **Session ID** — Secret token in browser (sessionStorage) sent with each request; never shown in UI or logs.
- **Handoff** — Short document passed between agents (e.g. planner → developer → tester): scope, decisions, what was done.
- **Trio** — The three agents for one domain: planner, developer, tester (e.g. frontend trio = frontend-planner, frontend-developer, frontend-tester).
- **Recovery key** — One-time secret shown once at setup; stored offline; can unlock the vault if you forget the master password. The app stores an encrypted copy of the master key unlockable with this key, not the recovery key itself.
- **max_length** — Server-side limit on string fields (username, title, notes, url, etc.) to prevent DoS and storage abuse. Enforced by Pydantic.

*(Add more terms as the app grows.)*
