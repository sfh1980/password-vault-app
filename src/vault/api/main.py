"""
FastAPI app: unlock, lock, CRUD folders/entries, password generation. Thin
handlers that call vault_db, audit, and session; no business logic in routes.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
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
    """Exactly one of password, recovery_key, or recovery_answers must be set."""
    password: str | None = Field(None, min_length=1)
    recovery_key: str | None = Field(None, min_length=1)
    recovery_answers: list[str] | None = Field(None, min_length=3, max_length=3)


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
    key_configured: bool = False
    questions_configured: bool = False
    questions: list[str] | None = None  # q1, q2, q3 when questions_configured


class RecoverySetupQuestionsRequest(BaseModel):
    question_1: str = Field(..., min_length=1)
    question_2: str = Field(..., min_length=1)
    question_3: str = Field(..., min_length=1)
    answer_1: str = Field(..., min_length=1)
    answer_2: str = Field(..., min_length=1)
    answer_3: str = Field(..., min_length=1)


class RecoveryQuestionsPublicResponse(BaseModel):
    """Returned by unauthenticated GET so unlock page can show question fields."""
    questions_configured: bool
    questions: list[str] | None = None  # [q1, q2, q3]


class GeneratePasswordQuery(BaseModel):
    length: int = Field(20, ge=8, le=128)
    upper: bool = True
    lower: bool = True
    digits: bool = True
    symbols: bool = True


class GeneratePasswordResponse(BaseModel):
    password: str


class VaultStatusResponse(BaseModel):
    initialized: bool


class SetupRequest(BaseModel):
    password: str = Field(..., min_length=1)


class ResetRequest(BaseModel):
    password: str = Field(..., min_length=1)


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


@app.get("/vault/status", response_model=VaultStatusResponse)
def get_vault_status():
    """Return whether the vault has been initialized (salt set). No auth required. Used to show setup vs login."""
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        salt = vault_db.get_salt(conn)
        return VaultStatusResponse(initialized=salt is not None)
    finally:
        conn.close()


@app.post("/setup", response_model=UnlockResponse)
def post_setup(body: SetupRequest):
    """First-time setup: initialize vault with master password, create first user, return session. Fails if vault already initialized. Audit: vault_setup."""
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        if vault_db.get_salt(conn) is not None:
            raise HTTPException(status_code=400, detail="Vault already initialized. Use Unlock to sign in.")
        salt = vault_db.init_salt(conn)
        key = derive_key(body.password.encode("utf-8"), salt)
        vault_db.set_password_check(conn, key)
        user_id = vault_db.get_or_create_first_user(conn)
        session_id = session_store.create_session(key, user_id)
        audit.log_event("vault_setup", resource_id=None, user_id=user_id)
        return UnlockResponse(session_id=session_id)
    finally:
        conn.close()


@app.post("/vault/reset")
def post_vault_reset(body: ResetRequest):
    """Reset vault: verify password, then delete the database file. Next visit will show first-time setup. For testing only. Audit: vault_reset."""
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        salt = vault_db.get_salt(conn)
        if salt is None:
            raise HTTPException(status_code=400, detail="Vault not initialized. Nothing to reset.")
        key = derive_key(body.password.encode("utf-8"), salt)
        user_id = vault_db.get_or_create_first_user(conn)
        verified = vault_db.verify_password_check(conn, key)
        if verified is False:
            raise HTTPException(status_code=401, detail="Wrong password.")
        if verified is None:
            try:
                folders = vault_db.get_folders(conn, key, user_id)
            except Exception:
                raise HTTPException(status_code=401, detail="Wrong password.")
            if not folders:
                raise HTTPException(
                    status_code=401,
                    detail="Cannot verify password for empty vault. Add a folder first or use the password from setup.",
                )
        audit.log_event("vault_reset", resource_id=None, user_id=user_id)
    finally:
        conn.close()
    db_path = Path(config.VAULT_DB_PATH)
    if db_path.is_file():
        os.remove(db_path)
    return JSONResponse(status_code=200, content={"message": "Vault reset. You can set up again."})


def _unlock_which(body: UnlockRequest) -> str:
    """Return 'password' | 'recovery_key' | 'recovery_answers' or raise 400."""
    has_pass = body.password is not None
    has_key = body.recovery_key is not None
    has_answers = body.recovery_answers is not None and len(body.recovery_answers) == 3
    if sum([has_pass, has_key, has_answers]) != 1:
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one: password, recovery_key, or recovery_answers (3 strings).",
        )
    if has_pass:
        return "password"
    if has_key:
        return "recovery_key"
    return "recovery_answers"


@app.post("/unlock", response_model=UnlockResponse)
def post_unlock(body: UnlockRequest):
    """Unlock with master password, recovery key, or 3 security-question answers. Returns session id."""
    which = _unlock_which(body)

    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        if which == "recovery_key":
            key = vault_db.unlock_with_recovery_key(conn, body.recovery_key.strip().encode("utf-8"))
            if key is None:
                raise HTTPException(status_code=400, detail="Invalid recovery key or recovery not set up.")
        elif which == "recovery_answers":
            a1, a2, a3 = body.recovery_answers[0].strip(), body.recovery_answers[1].strip(), body.recovery_answers[2].strip()
            key = vault_db.unlock_with_recovery_answers(conn, a1, a2, a3)
            if key is None:
                raise HTTPException(status_code=400, detail="Invalid answers or recovery questions not set up.")
        else:
            salt = vault_db.get_salt(conn)
            if salt is None:
                raise HTTPException(status_code=400, detail="Vault not initialized; run setup first.")
            key = derive_key(body.password.encode("utf-8"), salt)
        user_id = vault_db.get_or_create_first_user(conn)
        session_id = session_store.create_session(key, user_id)
        audit.log_event(
            "unlock_recovery_answers" if which == "recovery_answers" else ("unlock_recovery" if which == "recovery_key" else "unlock"),
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
    """Return recovery config: configured, key_configured, questions_configured, and questions if applicable."""
    _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        key_ok, qa_ok = vault_db.get_recovery_methods(conn)
        configured = key_ok or qa_ok
        questions = None
        if qa_ok:
            q1, q2, q3 = vault_db.get_recovery_questions(conn)
            questions = [q1, q2, q3]
        return RecoveryStatusResponse(
            configured=configured,
            key_configured=key_ok,
            questions_configured=qa_ok,
            questions=questions,
        )
    finally:
        conn.close()


@app.get("/recovery/questions", response_model=RecoveryQuestionsPublicResponse)
def get_recovery_questions_public():
    """Public endpoint so unlock page can show the 3 question fields when questions recovery is set. No auth."""
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        _, qa_ok = vault_db.get_recovery_methods(conn)
        questions = None
        if qa_ok:
            q1, q2, q3 = vault_db.get_recovery_questions(conn)
            questions = [q1, q2, q3]
        return RecoveryQuestionsPublicResponse(questions_configured=qa_ok, questions=questions)
    finally:
        conn.close()


@app.post("/recovery/setup-questions")
def post_recovery_setup_questions(
    body: RecoverySetupQuestionsRequest,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Store 3 security questions and wrap master key with key derived from answers. User must be unlocked. Audit: recovery_setup_questions."""
    key, user_id = _require_session(x_vault_session)
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        vault_db.set_recovery_questions(
            conn,
            key,
            body.question_1.strip(),
            body.question_2.strip(),
            body.question_3.strip(),
            body.answer_1,
            body.answer_2,
            body.answer_3,
        )
        audit.log_event("recovery_setup_questions", resource_id=None, user_id=user_id)
        return Response(status_code=204)
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
    """Serve the single-page vault UI. Disable cache so updates to HTML/CSS are visible."""
    response = FileResponse(_WEB_DIR / "index.html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


class NoCacheStaticFiles(StaticFiles):
    """Serve static files with no-cache so JS/CSS updates are visible during development."""

    def get_response(self, path: str, scope):
        response = super().get_response(path, scope)
        if hasattr(response, "headers"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response


app.mount("/static", NoCacheStaticFiles(directory=str(_WEB_DIR)), name="static")
