# Password Vault — Design Summary & Educational Implementation Plan

This document reviews your answers, fills in the gaps, recommends architecture and database choices, and outlines a **learning-focused** build plan. Each phase explains **why** we use certain code, **how** it fits together, and **which standards and practices** we follow.

---

## 1. Summary of Your Choices

| Area | Your choice | Implication |
|------|-------------|-------------|
| **Users** | 2 people, laptops (Ubuntu/Windows/iOS) + phones (Android/Apple) | We need multi-user support and later: web + native/mobile UIs. Start with web + CLI so all platforms can use the same backend. |
| **Use case** | Shared/family, apps/sites + sensitive data | Entries can be per-user or shared; we need folders and possibly sharing rules. |
| **Scale** | Tens to hundreds, scalable | SQLite is a good fit; we avoid over-engineering. |
| **Master password** | Single, maybe biometrics on mobile | We derive one key from the master password; biometrics = device-level unlock (later). |
| **Storage** | Docker container, backup to TrueNAS | App + DB live in Docker; a separate job syncs encrypted backups to TrueNAS. |
| **Security** | Bitwarden/LastPass level or stronger | AES-256-GCM, Argon2id for key derivation, constant-time comparisons, secure memory where possible. |
| **Session** | Industry standard | Configurable timeout (e.g. 5 / 15 / 60 min); default **15 minutes** inactivity. |
| **Clipboard** | Clear after 30 seconds | We implement a clipboard clear timer in each client (web, CLI, later mobile). |
| **UI** | Per-device + web, start simple | Phase 1: CLI + minimal web UI; later: better web + optional native/mobile. |
| **Python** | Latest stable | Target **Python 3.12+** (current stable). |
| **Dependencies** | Only what’s necessary | Minimal: `cryptography`, DB driver, web framework; add as we need. |
| **Database** | Your question | **Recommendation below.** |
| **Entry fields** | Title, username, password, URL, notes | Plus folders and attachments. |
| **Attachments** | Yes | Store encrypted blobs; metadata in DB. |
| **Folders** | Yes | Categories/folders for organization. |
| **Search** | All fields | Search over title, URL, username, tags, notes (indexed or in-app). |
| **Password generator** | Configurable per account | Length, character set (upper/lower/digits/symbols), and presets for common site rules. |
| **Sync/backup** | To TrueNAS | Daily (or configurable) job: export encrypted backup → push to TrueNAS. |
| **Backup** | Daily, rolling 30 days | Keep 30 daily backups; name by date; prune older. |
| **Recovery** | You want suggestions | **Options below.** |
| **Audit log** | Separate file, all events | Log to a dedicated audit file (or table + export); not inside the encrypted vault. |
| **Export** | No | No CSV/JSON export to reduce data leakage. |
| **Run** | Docker on Ubuntu homelab | Single Docker image (or compose) for app + DB. |
| **Install** | Single executable in Docker | Build with PyInstaller (or similar) inside Docker, or run as `python -m vault` in the image. |
| **Secrets in env** | Need guidance | **Guidance below.** |

---

## 2. Gaps Filled

### Session timeout (Q7)

There’s no single mandated value. Common practice is **configurable** options, e.g.:

- **1, 5, 15, 30, 60 minutes** (and “on restart” / “never” for dev only).

**Recommendation:** Default **15 minutes** inactivity; store the choice in config. We’ll implement this as: last-activity timestamp + a background or on-request check that locks the vault when the chosen interval has passed.

---

### Database recommendation (Q12)

Given:

- 2 users, tens to hundreds of entries, scalable
- Folders, attachments, search, audit in a separate store
- Running in Docker with backup to TrueNAS

**Recommendation: SQLite for the vault data.**

- **Why SQLite:** One file (e.g. `vault.db`), no separate server, perfect for “single container” and for backups (copy the file + encrypted copy to TrueNAS). Supports structured queries (folders, search, attachments metadata), and Python’s `sqlite3` is in the standard library.
- **Encryption:** The DB file will be encrypted at rest. Options:
  - **SQLCipher** (SQLite with transparent encryption), or
  - **Application-level:** store only encrypted blobs in SQLite and keep the key in memory (simpler to reason about and matches “unlock with master password”).
- **Practical approach for learning:** Start with **application-level encryption**: each “sensitive” column (e.g. password, notes, attachment blob) is encrypted with a key derived from the master password; the key lives only in memory while the vault is unlocked. SQLite then holds ciphertext plus metadata (id, folder_id, title, created_at, etc.). This teaches encryption boundaries and key lifecycle clearly.

**Storage layout:** App + SQLite DB inside the container; a volume for persistence; a cron or scheduled task inside (or beside) the container that runs daily, produces an encrypted backup file, and copies it to TrueNAS (e.g. SMB/NFS or rclone).

---

### Recovery strategy (Q20)

Options that fit a 2-person family vault:

1. **Recovery key/code (recommended)**  
   - At setup, we generate a **recovery key** (e.g. 24–32 random words or a long random string).  
   - The user stores it **offline** (paper, safe).  
   - If the master password is forgotten, they can unlock the vault with this key (we’d derive a decryption key from it and store a wrapped copy in the vault header).  
   - **Why:** No third party; you control the key; aligns with Bitwarden/1Password-style recovery.

2. **Emergency access (optional, later)**  
   - One person can invite the other as “emergency access.”  
   - The other requests access; after a waiting period (e.g. 48–72 hours) and no cancellation, they get access.  
   - **Why:** Good for “I’m unavailable” or “one person forgot the master password”; can be implemented after core vault is solid.

3. **Admin recovery (optional)**  
   - If you add an “admin” role, an admin could reset a user’s master password using a recovery key or escrow.  
   - Less critical for 2 users; can be a later phase.

**Recommendation:** Implement **(1) recovery key** in the first design: generated once, shown once, stored offline; used only when master password is lost. We’ll document this clearly in the app and in this repo.

---

### Secrets in env (Q25)

**Guidance:**

- **Production / normal use:** The master password should **not** come from the environment. It should be entered interactively (or via a secure UI) so it’s not written to process listings, shell history, or env dumps. **Best practice:** interactive only for humans.
- **Automation / scripting:** If you later want CI or scripts to unlock the vault (e.g. for backup verification), you *could* support reading the master password from a **file** with restricted permissions (e.g. `0400`) or from an env var, with a **big** warning in the docs and a config flag like `VAULT_ALLOW_ENV_MASTER_PASSWORD=1`. We’d still avoid logging it and clear it from memory when done.
- **Recovery key:** Same idea—prefer interactive entry; optional file/env for automation only, with clear documentation and opt-in.

**Recommendation for Phase 1:** **Interactive only.** Add optional env/file support in a later phase if you need it, with explicit docs and security caveats.

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Docker host (Ubuntu homelab)                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  password-vault-app container                                ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  ││
│  │  │  Web UI     │  │  CLI        │  │  Backend (FastAPI   │  ││
│  │  │  (browser)  │  │  (optional) │  │  or Flask + logic)  │  ││
│  │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  ││
│  │         │                │                     │             ││
│  │         └────────────────┼─────────────────────┘             ││
│  │                          │ HTTP / local sockets               ││
│  │                          ▼                                    ││
│  │  ┌─────────────────────────────────────────────────────────┐ ││
│  │  │  Core: crypto, key derivation, SQLite, audit logging     │ ││
│  │  └─────────────────────────────────────────────────────────┘ ││
│  │  ┌─────────────┐  ┌─────────────────────────────────────┐   ││
│  │  │  vault.db   │  │  audit.log (or audit DB + export)   │   ││
│  │  │  (volume)   │  │  (volume)                            │   ││
│  │  └─────────────┘  └─────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────┘│
│                          │                                       │
│                          │  Backup job (daily)                    │
│                          ▼                                       │
│  Encrypted backup file ──────────────► TrueNAS                   │
└─────────────────────────────────────────────────────────────────┘
```

- **Backend:** One process (e.g. FastAPI or Flask) handles auth (master password → key), CRUD for entries/folders/attachments, search, and password generation. It never writes the master password to disk; it derives a key and keeps it in memory.
- **Web UI:** Simple HTML/JS (or a minimal framework) that talks to the backend over HTTPS (reverse proxy in front) or over a bind to `127.0.0.1` only.
- **CLI:** Optional; can call the same backend over HTTP or use a shared library. Starting with the backend + web keeps the learning path focused.
- **Audit:** Every sensitive action (login, view entry, copy password, create/update/delete) is written to a separate audit log (file or DB), with no secrets in the log.

---

## 4. Standards & Practices We’ll Follow (and Why)

These are the standards and practices we’ll use so the code is consistent, maintainable, and educational.

### 4.1 Python style and structure

- **PEP 8** — Style guide for Python (naming, line length, spacing).  
  **Why:** Readable, consistent code; easy to collaborate and review.  
  **How:** We’ll follow it in every module; you can run `ruff` or `pycodestyle` in the repo.

- **Type hints (PEP 484)** — Annotations on function parameters and return types.  
  **Why:** Documents contracts, catches bugs early, better editor support.  
  **How:** We use `str`, `int`, `list[Entry]`, `Optional[str]`, etc.; no `Any` unless necessary.

- **Docstrings (PEP 257)** — Module, class, and function docstrings.  
  **Why:** Explains “why” and “how” at the call site.  
  **How:** One-line or short multi-line; mention side effects (e.g. “writes to audit log”).

- **Single responsibility** — Each module/class has one clear job (e.g. `crypto.py`, `vault_db.py`, `audit.py`).  
  **Why:** Easier to test and to understand.  
  **How:** We split “key derivation,” “encrypt/decrypt,” “DB access,” “audit,” “API routes.”

### 4.2 Security

- **Constant-time comparison** for passwords/tokens (e.g. `hmac.compare_digest`).  
  **Why:** Avoids timing side channels.  
  **How:** Every comparison of secrets uses the standard library’s constant-time helper.

- **Argon2id** for key derivation from the master password.  
  **Why:** OWASP and NIST recommend memory-hard KDFs to slow brute force.  
  **How:** We use the `cryptography` library (or a dedicated Argon2 binding) with safe parameters.

- **AES-256-GCM** for encrypting sensitive fields.  
  **Why:** Authenticated encryption; industry standard.  
  **How:** One key per vault session; nonce/IV per encryption; we never reuse nonces.

- **No secrets in logs** — Audit log has event types and identifiers, never passwords or keys.  
  **Why:** Prevents credential leakage in log files.  
  **How:** Audit module accepts only event type + resource id + timestamp (+ optional user id).

### 4.3 Project layout

- **Explicit dependency list** — `requirements.txt` (and optionally `pyproject.toml`) with pinned versions.  
  **Why:** Reproducible builds and safe updates.  
  **How:** We add only what we need; we document why each dependency is there.

- **Configuration via env or config file** — No secrets in code; paths and timeouts in config.  
  **Why:** Same image can run in dev vs prod; secrets stay out of repo.  
  **How:** e.g. `VAULT_DB_PATH`, `VAULT_SESSION_TIMEOUT_MINUTES`, `VAULT_AUDIT_LOG_PATH`.

---

## 5. Educational Implementation Plan (Phased)

Each phase focuses on a few concepts, with “why,” “how,” and “standards” called out.

---

### Phase 1 — Core crypto and data model (foundation)

**Goal:** Master password → key; encrypt/decrypt one blob; understand key lifecycle.

**What we’ll build:**

- Small CLI or script that:  
  - Prompts for master password.  
  - Derives a key with Argon2id.  
  - Encrypts a single “vault blob” (e.g. JSON of entries) with AES-256-GCM.  
  - Writes encrypted file to disk; reads it back and decrypts.

**Concepts and practices:**

- **Why Argon2id:** Slows down brute force; we’ll set time and memory parameters and explain them in comments.
- **Why AES-GCM:** Authenticated encryption; we’ll show nonce generation and why we never reuse.
- **Why one key in memory:** Key is created at unlock and cleared at lock; we’ll show where it’s created and where it’s zeroed (or garbage-collected).
- **Standards:** PEP 8, type hints, docstrings; one module for KDF, one for encrypt/decrypt; constant-time comparison for any password check.

**Deliverable:** `crypto.py` + small `main.py` (or `python -m vault.cli`) that round-trips one encrypted file.

---

### Phase 2 — SQLite schema and application-level encryption

**Goal:** Persist entries and folders in SQLite; encrypt sensitive columns only.

**What we’ll build:**

- Schema: `users`, `folders`, `entries`, `attachments` (id, owner, folder_id, encrypted_title, encrypted_username, encrypted_password, encrypted_notes, url_plaintext_or_encrypted, created_at, etc.).
- `vault_db.py`: open DB, run migrations (e.g. raw SQL or a tiny migration runner), insert/update/select; all sensitive fields go in/out as bytes (encrypted).
- `crypto.py` (from Phase 1): encrypt/decrypt per field or per row; key still from master password, held in memory.

**Concepts and practices:**

- **Why SQLite:** Single file, no server, good for learning and for Docker + backup.
- **Why encrypt per field/row:** So we can still query by id/folder/created_at without decrypting everything; we’ll document which columns are plain and which are ciphertext.
- **Why migrations:** So we can change schema later without losing data; we’ll use a simple “version” table and ordered SQL scripts.
- **Standards:** Type hints on all public functions; docstrings for “what this table/column stores”; PEP 8; no raw SQL in API layer—only in `vault_db.py`.

**Deliverable:** Schema + `vault_db.py` + minimal script that creates a user, folder, and one entry (encrypted), then reads it back.

---

### Phase 3 — Backend API and audit logging

**Goal:** REST (or RPC) API for unlock, lock, CRUD entries/folders, search, password generation; every action audited.

**What we’ll build:**

- Small FastAPI (or Flask) app: routes for `POST /unlock`, `POST /lock`, `GET /folders`, `GET /entries`, `POST /entries`, etc. Session = in-memory key + optional session id; timeout enforced on each request.
- `audit.py`: `log_event(event_type, resource_id, user_id=None)`. Writes to a file or to an audit table; no secrets.
- Password generator: function that takes length + character-set flags; used by API and later by UI.

**Concepts and practices:**

- **Why FastAPI/Flask:** Simple HTTP API; FastAPI gives automatic docs and validation—good for learning.
- **Why session in memory:** No JWT with secrets; key stays server-side; we’ll explain the tradeoff vs stateless JWT.
- **Why separate audit:** So we never log secrets; audit is the single place that records “who did what when.”
- **Standards:** Route handlers thin (parse request → call core → return); business logic in a “service” layer; PEP 8, type hints, docstrings; audit call on every sensitive action.

**Deliverable:** API server + audit log; can unlock and CRUD entries via curl/Postman.

---

### Phase 4 — Minimal web UI and clipboard/session behavior

**Goal:** Simple UI to login, list folders/entries, view/copy password, create entry; session timeout and clipboard clear.

**What we’ll build:**

- Static HTML/JS (or one minimal framework) that calls the API; login form → store session cookie or token; list and detail views; “copy password” button.
- Session timeout: front-end timer that calls `POST /lock` or clears state after N minutes of inactivity; optionally backend re-checks last activity.
- Clipboard: on copy, set a 30-second timer then clear clipboard (e.g. `navigator.clipboard.writeText('')`); document that we don’t keep the password in JS longer than needed.

**Concepts and practices:**

- **Why minimal UI first:** Focus on security and API; we can make it pretty later.
- **Why we clear clipboard:** Your requirement; we’ll implement it and note the limitation (other apps could read clipboard in that 30s window).
- **Standards:** No passwords in JS longer than necessary; no secrets in console.log; HTTPS in production (reverse proxy).

**Deliverable:** Web UI that works with the API; session timeout and 30s clipboard clear.

---

### Phase 5 — Docker, backup to TrueNAS, recovery key

**Goal:** Run the app in Docker; daily encrypted backup; recovery key flow.

**What we’ll build:**

- Dockerfile: Python 3.12, install deps, copy app, run `uvicorn` or `gunicorn`; volume for `vault.db` and audit log.
- Backup script/job: dump or copy `vault.db` (or export encrypted blob), encrypt with a backup key or the same key, upload to TrueNAS (e.g. rclone or SMB); retain last 30; run daily via cron in container or host.
- Recovery key: at first unlock, optionally generate recovery key; show once; store a wrapped key in vault header; add “Unlock with recovery key” path that uses it to derive the same decryption key.

**Concepts and practices:**

- **Why Docker:** Matches your environment; reproducible; we’ll document the image and volume layout.
- **Why encrypt backup:** So the file on TrueNAS is useless without the key; we’ll document where the key is stored (e.g. only in the app or in a separate secret).
- **Why recovery key:** Your request; we implement it so you can recover without the master password, with the key stored offline.
- **Standards:** Dockerfile multi-stage if we need a smaller image; env-based config; no secrets in Dockerfile or image.

**Deliverable:** `docker-compose.yml` (or run instructions), backup job, recovery key generation and unlock.

---

### Phase 6+ (later)

- **Attachments:** Store encrypted blobs in DB or object store; metadata in `attachments` table; API to upload/download.
- **Multi-user:** Separate users table; each user has own key or shared key model; folder sharing.
- **Biometrics on mobile:** Use device APIs to unlock a local key; out of scope for the first Python backend but we’ll keep the API ready (e.g. session or token from mobile app).
- **Presets for password generator:** Predefined length/charset per “site type” (e.g. “banking,” “social”); configurable in UI.

---

## 6. Dependency Plan (minimal and justified)

| Dependency | Purpose | Why not stdlib |
|------------|--------|-----------------|
| `cryptography` | Argon2 (or passlib), AES-GCM | Stdlib has no Argon2 and low-level AES; `cryptography` is the standard choice. |
| `fastapi` + `uvicorn` | HTTP API and ASGI server | Simple, async-capable, automatic OpenAPI; good for learning. |
| `pydantic` | Request/response validation | Comes with FastAPI; keeps validation in one place. |
| `sqlite3` | Database | Stdlib; no extra dependency. |
| (optional) `passlib` | Argon2 only | If we want Argon2 and `cryptography` doesn’t cover it; otherwise we use `cryptography`’s hazmat or a small Argon2 binding. |

We’ll add more only when needed (e.g. rclone for TrueNAS, or a front-end build tool).

---

## 7. File Layout (target)

```
password-vault-app/
├── README.md
├── DESIGN_AND_EDUCATION.md   # this file
├── PASSWORD_VAULT_QUESTIONS.md
├── requirements.txt
├── pyproject.toml            # optional, for ruff/typing
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── src/
│   └── vault/
│       ├── __init__.py
│       ├── crypto.py         # KDF, encrypt, decrypt
│       ├── vault_db.py       # SQLite schema, migrations, CRUD
│       ├── audit.py          # audit log
│       ├── generator.py      # password generator
│       ├── config.py         # load from env
│       ├── api/
│       │   ├── __init__.py
│       │   ├── main.py       # FastAPI app, routes
│       │   └── session.py    # in-memory session, timeout
│       └── cli.py            # optional CLI entry
├── migrations/               # SQL migrations
│   ├── 001_initial.sql
│   └── ...
├── scripts/
│   └── backup_to_truenas.sh  # or .py
└── web/                      # minimal static UI
    ├── index.html
    └── app.js
```

---

## 8. Next Step

Once you’re happy with this design, the next step is **Phase 1**: implement `crypto.py` and a tiny script that round-trips one encrypted vault file, with docstrings and comments that explain *why* each step (Argon2id params, GCM nonce, constant-time compare). I’ll use this document and your answers in `PASSWORD_VAULT_QUESTIONS.md` as the single source of truth for requirements and education focus.

If you want to adjust anything (e.g. default session timeout, recovery key UX, or which phase to do first), say what you’d like changed and we’ll update this doc and proceed accordingly.
