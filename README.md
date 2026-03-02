# Password Vault

Family password vault: self-hosted, encrypted, backup to TrueNAS.

**Documentation:** See **[DOCS.md](DOCS.md)** for the full table of contents. Main entries: [User guide](USER_GUIDE.md) (run and use the app); [Deploy and operations](DEPLOY_AND_OPERATIONS.md) (Docker, Nginx, backup); [Developer reference](DEVELOPER_REFERENCE.md) (API, status, tests, glossary); [Agents and workflow](AGENTS_AND_WORKFLOW.md); [Educational code walkthrough](EDUCATIONAL_CODE_WALKTHROUGH.md).

**Current phase:** Phase 4 (web UI) done → Phase 5 (Docker, backup, recovery key).

**Run:** `python -m vault.cli` (Phase 1); `python scripts/phase2_demo.py` (Phase 2); `uvicorn vault.api.main:app --port 8001` (Phase 3 API + Phase 4 web UI at http://127.0.0.1:8001/).

---

## Prerequisites

- **Python 3.12+** (current stable).
- **Ubuntu/Debian:** The standard `python3` package does not include full venv support. Install:
  ```bash
  sudo apt install python3.12-venv
  ```
  so `python3 -m venv .venv` creates a complete environment (with `bin/activate`, `pip`, etc.).

## Local setup

From the project root:

```bash
cd "/home/sean/Cursor Projects/password-vault-app"
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .   # install vault package in editable mode so "python -m vault.cli" works
```

To run the Phase 1 round-trip script (encrypt a blob to a file, read it back, decrypt):

```bash
python -m vault.cli
```

You’ll be prompted for a master password; the script writes `demo_vault.blob` in the project root, then reads it back and verifies decryption.

To run the Phase 2 demo (SQLite + encrypted user/folder/entry, then read-back):

```bash
python scripts/phase2_demo.py
```

Creates `demo_vault.db` in the project root (ignored by git); first run initializes the vault salt, then creates one user, folder, and entry and verifies decryption.

### Phase 3 — API server

Start the API (use the same DB as Phase 2 so you can unlock with the demo password). We use **port 8001** so it doesn’t conflict with Portainer (which often uses 8000 in Docker):

```bash
VAULT_DB_PATH=demo_vault.db uvicorn vault.api.main:app --host 127.0.0.1 --port 8001
```

Then open http://127.0.0.1:8001/docs for Swagger UI, or use curl:

```bash
# Unlock (returns session_id; use your username)
curl -X POST http://127.0.0.1:8001/unlock -H "Content-Type: application/json" -d '{"username":"YOUR_USERNAME","password":"YOUR_MASTER_PASSWORD"}'

# List folders (replace SESSION_ID with the session_id from unlock)
curl -H "X-Vault-Session: SESSION_ID" http://127.0.0.1:8001/folders

# List entries in folder 1
curl -H "X-Vault-Session: SESSION_ID" "http://127.0.0.1:8001/entries?folder_id=1"

# Create entry, generate password, lock
curl -X POST http://127.0.0.1:8001/entries -H "X-Vault-Session: SESSION_ID" -H "Content-Type: application/json" -d '{"folder_id":1,"title":"New site","username":"me@example.com","password":"","notes":"","url":"https://example.com"}'
curl -H "X-Vault-Session: SESSION_ID" "http://127.0.0.1:8001/generate-password?length=20"
curl -X POST http://127.0.0.1:8001/lock -H "X-Vault-Session: SESSION_ID"
```

Config (env): `VAULT_DB_PATH` (default `vault.db`), `VAULT_SESSION_TIMEOUT_MINUTES` (default 15), `VAULT_AUDIT_LOG_PATH` (default `audit.log`).

### Phase 4 — Web UI

The same server serves the API and the web UI. Open **http://127.0.0.1:8001/** in a browser:

- **Login:** Enter master password to unlock; session is stored in `sessionStorage` and sent as `X-Vault-Session` on every request.
- **Session timeout:** After 15 minutes of inactivity the UI calls `POST /lock` and shows the login screen again.
- **Clipboard:** When you click “Copy password,” the password is copied to the clipboard and cleared automatically after 30 seconds.
- **Folders & entries:** List folders, click one to list entries, click an entry to view details or copy password; use “Add entry” to create a new entry (with optional “Generate” for a random password).
