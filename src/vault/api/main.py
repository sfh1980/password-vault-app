"""
FastAPI app: unlock, lock, CRUD folders/entries, password generation. Thin
handlers that call vault_db, audit, and session; no business logic in routes.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vault import audit, config, vault_db
from vault.api import session as session_store
from vault.crypto import ARGON2_SALT_LEN, derive_key, encrypt, random_bytes
from vault.generator import generate_password

app = FastAPI(title="Password Vault API", version="0.1.0")

# Apply config at import so session timeout is set before first request
session_store.set_timeout_minutes(config.VAULT_SESSION_TIMEOUT_MINUTES)

# --- Request/response models (no secrets in docs) ---


class UnlockRequest(BaseModel):
    """Exactly one of password or recovery_key must be set."""
    password: str | None = Field(None, min_length=1)
    recovery_key: str | None = Field(None, min_length=1)


class UnlockResponse(BaseModel):
    session_id: str


class CreateFolderRequest(BaseModel):
    name: str = Field(..., min_length=1)


class CreateFolderResponse(BaseModel):
    id: int


class CreateEntryRequest(BaseModel):
    folder_id: int
    title: str = Field(..., min_length=1)
    username: str = ""
    password: str = ""
    notes: str = ""
    url: str = ""


class CreateEntryResponse(BaseModel):
    id: int


class UpdateEntryRequest(BaseModel):
    """All fields optional; only provided fields are updated."""
    title: str | None = None
    username: str | None = None
    password: str | None = None
    notes: str | None = None
    url: str | None = None


class RecoverySetupResponse(BaseModel):
    """Recovery key shown once; user must store it offline."""
    recovery_key: str


class RecoveryStatusResponse(BaseModel):
    configured: bool


class GeneratePasswordQuery(BaseModel):
    length: int = Field(20, ge=8, le=128)
    upper: bool = True
    lower: bool = True
    digits: bool = True
    symbols: bool = True


class GeneratePasswordResponse(BaseModel):
    password: str


# --- Helpers ---


def _require_session(x_vault_session: str | None = Header(None, alias="X-Vault-Session")) -> tuple[bytes, int]:
    """Return (key, user_id) or raise 401."""
    if not x_vault_session:
        raise HTTPException(status_code=401, detail="Missing X-Vault-Session header")
    out = session_store.get_session(x_vault_session)
    if not out:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return out


# --- Routes ---


@app.post("/unlock", response_model=UnlockResponse)
def post_unlock(body: UnlockRequest):
    """Unlock with master password or recovery key. Returns session id. Audit: unlock or unlock_recovery."""
    if body.password is not None and body.recovery_key is not None:
        raise HTTPException(status_code=400, detail="Provide either password or recovery_key, not both.")
    if body.password is None and body.recovery_key is None:
        raise HTTPException(status_code=400, detail="Provide password or recovery_key.")

    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        if body.recovery_key is not None:
            key = vault_db.unlock_with_recovery_key(conn, body.recovery_key.strip().encode("utf-8"))
            if key is None:
                raise HTTPException(status_code=400, detail="Invalid recovery key or recovery not set up.")
        else:
            salt = vault_db.get_salt(conn)
            if salt is None:
                raise HTTPException(status_code=400, detail="Vault not initialized; run Phase 2 demo or init first.")
            key = derive_key(body.password.encode("utf-8"), salt)
        user_id = vault_db.get_or_create_first_user(conn)
        session_id = session_store.create_session(key, user_id)
        audit.log_event(
            "unlock_recovery" if body.recovery_key is not None else "unlock",
            resource_id=None,
            user_id=user_id,
        )
        return UnlockResponse(session_id=session_id)
    finally:
        conn.close()


@app.post("/lock")
def post_lock(x_vault_session: str | None = Header(None, alias="X-Vault-Session")):
    """Discard the session (lock). Audit: lock."""
    if x_vault_session:
        session_store.delete_session(x_vault_session)
    audit.log_event("lock", resource_id=None)
    return Response(status_code=204)  # No Content: no body


@app.get("/folders")
def get_folders(x_vault_session: str | None = Header(None, alias="X-Vault-Session")):
    """List folders for the current user."""
    key, user_id = _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        folders = vault_db.get_folders(conn, key, user_id)
        audit.log_event("list_folders", resource_id=None, user_id=user_id)
        return folders
    finally:
        conn.close()


@app.post("/folders", response_model=CreateFolderResponse)
def post_folder(
    body: CreateFolderRequest,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Create a folder. Audit: create_folder."""
    key, user_id = _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        folder_id = vault_db.create_folder(conn, key, user_id, body.name.strip())
        audit.log_event("create_folder", resource_id=folder_id, user_id=user_id)
        return CreateFolderResponse(id=folder_id)
    finally:
        conn.close()


@app.get("/entries")
def get_entries(
    folder_id: int,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """List entries in a folder."""
    key, user_id = _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        entries = vault_db.get_entries(conn, key, folder_id)
        audit.log_event("list_entries", resource_id=folder_id, user_id=user_id)
        return entries
    finally:
        conn.close()


@app.get("/search")
def search_entries(
    q: str = "",
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Search entries by title, username, notes, or URL (case-insensitive). Returns list of entries with folder_id and folder_name. Empty q returns []."""
    key, user_id = _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        results = vault_db.search_entries(conn, key, user_id, q)
        audit.log_event("search", resource_id=None, user_id=user_id)
        return results
    finally:
        conn.close()


@app.post("/entries", response_model=CreateEntryResponse)
def post_entry(
    body: CreateEntryRequest,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Create an entry in a folder. Audit: create_entry."""
    key, user_id = _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        entry_id = vault_db.create_entry(
            conn,
            key,
            body.folder_id,
            title=body.title,
            username=body.username,
            password=body.password,
            notes=body.notes,
            url=body.url,
        )
        audit.log_event("create_entry", resource_id=entry_id, user_id=user_id)
        return CreateEntryResponse(id=entry_id)
    finally:
        conn.close()


@app.patch("/entries/{entry_id}")
def patch_entry(
    entry_id: int,
    body: UpdateEntryRequest,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Update an entry by id. Audit: update_entry. Returns 204 on success, 404 if not found or not owned."""
    key, user_id = _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        ok = vault_db.update_entry(
            conn,
            key,
            entry_id,
            user_id,
            title=body.title,
            username=body.username,
            password=body.password,
            notes=body.notes,
            url=body.url,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="Entry not found")
        audit.log_event("update_entry", resource_id=entry_id, user_id=user_id)
        return Response(status_code=204)
    finally:
        conn.close()


@app.delete("/entries/{entry_id}")
def delete_entry_route(
    entry_id: int,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Delete an entry by id. Audit: delete_entry. Returns 204 on success, 404 if not found or not owned."""
    key, user_id = _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        ok = vault_db.delete_entry(conn, entry_id, user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Entry not found")
        audit.log_event("delete_entry", resource_id=entry_id, user_id=user_id)
        return Response(status_code=204)
    finally:
        conn.close()


@app.post("/recovery/setup", response_model=RecoverySetupResponse)
def post_recovery_setup(
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Generate and store recovery key. User must be unlocked. Returns recovery_key once; user must store it offline. Audit: recovery_setup."""
    key, user_id = _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        recovery_key = secrets.token_hex(32)
        recovery_salt = random_bytes(ARGON2_SALT_LEN)
        recovery_derived = derive_key(recovery_key.encode("utf-8"), recovery_salt)
        wrapped = encrypt(recovery_derived, key)
        vault_db.set_recovery(conn, recovery_salt, wrapped)
        audit.log_event("recovery_setup", resource_id=None, user_id=user_id)
        return RecoverySetupResponse(recovery_key=recovery_key)
    finally:
        conn.close()


@app.get("/recovery/status", response_model=RecoveryStatusResponse)
def get_recovery_status(
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Return whether recovery key is configured (for current vault)."""
    _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        configured = vault_db.get_recovery_configured(conn)
        return RecoveryStatusResponse(configured=configured)
    finally:
        conn.close()


@app.get("/generate-password", response_model=GeneratePasswordResponse)
def get_generate_password(
    length: int = 20,
    upper: bool = True,
    lower: bool = True,
    digits: bool = True,
    symbols: bool = True,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Generate a random password; requires an active session."""
    _require_session(x_vault_session)
    password = generate_password(length=length, upper=upper, lower=lower, digits=digits, symbols=symbols)
    return GeneratePasswordResponse(password=password)


# --- Phase 4: serve web UI (after API routes so they take precedence) ---

_WEB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web"


@app.get("/", response_class=FileResponse)
def get_index():
    """Serve the single-page vault UI."""
    return FileResponse(_WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")
