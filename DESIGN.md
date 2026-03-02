# Design and planning

Combined design, requirements, agents/rules, and domain integration. For the full doc index see [DOCS.md](DOCS.md).

---

## Table of contents

1. [Design summary and education](#1-design-summary-and-education)
2. [Password vault Q&A](#2-password-vault-qa)
3. [Agents and rules design](#3-agents-and-rules-design)
4. [Domain integration (whoissean.dev)](#4-domain-integration-whoisseandev)

---

## 1. Design summary and education

*Source: consolidated from DESIGN_AND_EDUCATION.md.*

This section reviews your choices, fills in gaps, recommends architecture and database, and outlines a learning-focused build plan.

### Summary of your choices

| Area | Your choice | Implication |
|------|-------------|-------------|
| **Users** | 2 people, laptops (Ubuntu/Windows/iOS) + phones (Android/Apple) | Multi-user support; web + native/mobile UIs later. Start with web + CLI. |
| **Use case** | Shared/family, apps/sites + sensitive data | Entries per-user or shared; folders and possibly sharing rules. |
| **Scale** | Tens to hundreds, scalable | SQLite is a good fit. |
| **Master password** | Single, maybe biometrics on mobile | One key from master password; biometrics = device-level unlock (later). |
| **Storage** | Docker container, backup to TrueNAS | App + DB in Docker; sync encrypted backups to TrueNAS. |
| **Security** | Bitwarden/LastPass level or stronger | AES-256-GCM, Argon2id, constant-time compare. |
| **Session** | Industry standard | Configurable timeout; default 15 minutes. |
| **Clipboard** | Clear after 30 seconds | Implement in each client (web, CLI, later mobile). |
| **Database** | Your question | Recommendation: SQLite with application-level encryption. |
| **Recovery** | You want suggestions | Recovery key (recommended) + optional emergency access later. |

### Gaps filled

- **Session timeout:** Default **15 minutes**; configurable.
- **Database:** **SQLite** with application-level encryption (sensitive columns as encrypted blobs; key in memory).
- **Recovery:** **Recovery key** generated once, shown once, stored offline; used when master password is lost.
- **Secrets in env:** **Interactive only** for production; optional env/file for automation in a later phase with clear docs.

### High-level architecture

- **Backend:** One process (FastAPI) handles auth, CRUD, search, password generation. Key from master password; never written to disk.
- **Web UI:** Simple HTML/JS; talks to backend over HTTPS (reverse proxy) or 127.0.0.1.
- **Audit:** Every sensitive action logged to a separate audit log (no secrets).

### Standards and practices

- **Python:** PEP 8, type hints, docstrings, single responsibility.
- **Security:** Constant-time comparison, Argon2id, AES-256-GCM, no secrets in logs.
- **Config:** Env or config file; no secrets in code.

### Phased implementation (summary)

- **Phase 1:** Core crypto and data model (key derivation, encrypt/decrypt one blob).
- **Phase 2:** SQLite schema and application-level encryption.
- **Phase 3:** Backend API and audit logging.
- **Phase 4:** Minimal web UI, session timeout, clipboard clear.
- **Phase 5:** Docker, backup to TrueNAS, recovery key.
- **Phase 6+:** Attachments, multi-user refinements, biometrics, presets.

---

## 2. Password vault Q&A

*Source: consolidated from PASSWORD_VAULT_QUESTIONS.md.*

Answers used to design the vault.

### Scope and use case

- **Who:** Initially 2 people; Ubuntu, Windows, iOS laptops; Android and Apple phones.
- **Use case:** Shared/family; logins for apps/sites and other sensitive data.
- **Scale:** Tens to hundreds; easily scalable.

### Security and cryptography

- **Master password:** Single master password; maybe biometrics on mobile.
- **Storage:** Docker container with backup on TrueNAS.
- **Encryption:** Industry standard (Bitwarden/LastPass level or stronger).
- **Session timeout:** Industry standard (we use 15 min default).
- **Clipboard:** Clear after 30 seconds.

### Tech stack and platform

- **Interface:** Per-device and web; start simple.
- **Python:** Latest stable (3.12+).
- **Dependencies:** Only what’s necessary.
- **Database:** Recommendation from design doc: SQLite with app-level encryption.

### Data model and features

- **Fields:** Title, username, password, URL, notes.
- **Attachments:** Yes.
- **Folders/categories:** Yes.
- **Search:** All of the above.
- **Password generator:** Configurable (length, character set, presets).

### Sync, backup, recovery

- **Sync/backup:** To TrueNAS; daily; rolling 30 days.
- **Recovery:** Recovery strategy; options in design doc.

### Access control and audit

- **Audit log:** Separate file; all events.
- **Export:** No.

### Deployment and environment

- **Where:** Docker on Ubuntu homelab.
- **Install:** Single executable in Docker (or run from source in container).
- **Secrets in env:** Guidance in design doc (interactive only for production).

---

## 3. Agents and rules design

*Source: consolidated from AGENTS_AND_RULES_DESIGN.md.*

### How Cursor subagents work

- **Single level:** Main Agent invokes subagents; they do not launch others.
- **Handoffs:** Structured output (e.g. markdown in repo) passed sequentially: Planner → Developer → Tester; then integration-reviewer across domains.

### Agent roster (13 total)

**Frontend (3):** frontend-planner, frontend-developer, frontend-tester.

**Backend (3):** backend-planner, backend-developer, backend-tester.

**Database (3):** database-planner, database-developer, database-tester.

**Cross-domain (4):** integration-reviewer, security-auditor, verifier, documentation-educator.

### Handoff format

Location: `docs/handoffs/` (e.g. `frontend-YYYYMMDD.md`). Structure: Scope, Decisions, Implemented, Test results, Open/deferred. Integration-reviewer produces a master decision doc.

### .cursor additions

- **Rules:** project-context, orchestration, frontend/backend/database/security/testing/documentation standards.
- **Agents:** `.cursor/agents/` with name, description, optional model/readonly.

### Decisions summary (locked in)

| Ref | Decision |
|-----|----------|
| F1 | Use all 13 agents from the start. |
| F2 | Main Agent explicitly asks ("Proceed?") before starting a trio. |
| F3 | One instruction → Agent runs planner → developer → tester in one go. |
| F4 | Ask "Do you want to git commit?" after each domain trio. |
| F5 | If tester says refactor needed: present to user and wait. |
| F6 | Tests that only read main DB are fine; if changes needed, consult user. |
| F7 | User answers in own words for reassignment. |
| F8 | documentation-educator: only USER_GUIDE (HOW_IT_WORKS) + glossary until "completion." |
| F9 | Glossary in separate VOCAB (see [Developer reference](DEVELOPER_REFERENCE.md#glossary-vocab)). |
| F10 | Main Agent asks first before running security-auditor. |
| F11 | Any new frontend library/framework → always send for approval. |
| F12 | Migrations: up + down when possible. |
| F13 | Written API contract (see [Developer reference](DEVELOPER_REFERENCE.md#api-contract)). |
| F14 | Status note in docs/agent-status.md (see [Agents and workflow](AGENTS_AND_WORKFLOW.md)). |
| F15 | Short handoffs; verifier on critical path; planners/testers output only what next agent needs. |
| F16 | Standard: `tests/` directory, `pytest tests/` from repo root with venv. |

---

## 4. Domain integration (whoissean.dev)

*Source: consolidated from WHOISSEAN_INTEGRATION.md.*

### Can the full app run on whoissean.dev?

**No.** whoissean.dev is a Jekyll static site on GitHub Pages; it does not run Python or a backend. The vault backend must run on your homelab (Docker).

### Options for “piggybacking”

- **Option A (recommended):** Run the full vault at **vault.whoissean.dev** (Docker on homelab). Add DNS for subdomain; add a link on whoissean.dev to `https://vault.whoissean.dev`.
- **Option B:** Host static vault UI in the Jekyll repo at e.g. whoissean.dev/vault/; UI calls API at vault.whoissean.dev. Requires CORS and token-based auth.
- **Option C:** Link only: vault runs anywhere; whoissean.dev has a link to it.

### What you need for Option A

- **DNS:** A or CNAME for `vault.whoissean.dev` to your homelab (or tunnel).
- **Homelab:** Vault in Docker; Nginx + TLS or Cloudflare Tunnel.
- **whoissean.dev:** Add nav link or page to `https://vault.whoissean.dev`.

See [Deploy and operations](DEPLOY_AND_OPERATIONS.md#deploy-docker-nginx-and-vaultwhoisseandev) for Nginx, Certbot, and TLS steps.
