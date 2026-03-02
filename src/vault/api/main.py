"""
FastAPI app: unlock, lock, CRUD folders/entries, password generation. Thin
handlers that call vault_db, audit, and session; no business logic in routes.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vault import audit, config, vault_db
from vault.api import rate_limit, session as session_store
from vault.crypto import derive_key
from vault.generator import generate_password

# Application logging (no secrets). Level from config after config is loaded.
_logger = logging.getLogger("vault")

# Optional Sentry before app creation so we capture all errors
if config.VAULT_SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        def _sentry_before_send(event, hint):
            # Strip any request body that might contain password/key
            if "request" in event and event["request"]:
                if isinstance(event["request"].get("data"), dict):
                    for k in ("password", "recovery_key", "recovery_answers", "confirm"):
                        if k in event["request"]["data"]:
                            event["request"]["data"][k] = "[REDACTED]"
            return event

        sentry_sdk.init(
            dsn=config.VAULT_SENTRY_DSN,
            integrations=[FastApiIntegration()],
            before_send=_sentry_before_send,
            traces_sample_rate=0,
        )
        _sentry_enabled = True
    except Exception:  # noqa: BLE001
        _sentry_enabled = False
else:
    _sentry_enabled = False


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup: validate config, set logging, log ready. Shutdown: log and drain."""
    config.validate_config()
    logging.basicConfig(
        level=getattr(logging, config.VAULT_LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    session_store.set_timeout_minutes(config.VAULT_SESSION_TIMEOUT_MINUTES)
    rate_limit.set_window_seconds(60.0)
    _logger.info("Vault app starting")
    yield
    _logger.info("Vault app shutting down")


app = FastAPI(title="Password Vault API", version="0.1.0", lifespan=_lifespan)

# CORS: same-origin only if VAULT_CORS_ORIGINS empty; else allow listed origins
_origins = [o.strip() for o in config.VAULT_CORS_ORIGINS.split(",") if o.strip()] if config.VAULT_CORS_ORIGINS else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Vault-Session"],
)

# --- Request/response models (no secrets in docs) ---


class UnlockRequest(BaseModel):
    """Username required. Exactly one of password, recovery_key, or recovery_answers must be set."""
    username: str = Field(..., min_length=1, max_length=64)
    password: str | None = Field(None, min_length=1)
    recovery_key: str | None = Field(None, min_length=1)
    recovery_answers: list[str] | None = Field(None, min_length=3, max_length=3)


class UnlockResponse(BaseModel):
    session_id: str


class CreateFolderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)


class CreateFolderResponse(BaseModel):
    id: int


class CreateEntryRequest(BaseModel):
    folder_id: int
    title: str = Field(..., min_length=1, max_length=256)
    username: str = Field("", max_length=256)
    password: str = Field("", max_length=512)
    notes: str = Field("", max_length=4096)
    url: str = Field("", max_length=2048)


class CreateEntryResponse(BaseModel):
    id: int


class UpdateEntryRequest(BaseModel):
    """All fields optional; only provided fields are updated."""
    title: str | None = Field(None, max_length=256)
    username: str | None = Field(None, max_length=256)
    password: str | None = Field(None, max_length=512)
    notes: str | None = Field(None, max_length=4096)
    url: str | None = Field(None, max_length=2048)


class RecoverySetupResponse(BaseModel):
    """Recovery key shown once; user must store it offline."""
    recovery_key: str


class RecoveryStatusResponse(BaseModel):
    configured: bool
    key_configured: bool = False
    questions_configured: bool = False
    questions: list[str] | None = None  # q1, q2, q3 when questions_configured


class RecoverySetupQuestionsRequest(BaseModel):
    question_1: str = Field(..., min_length=1, max_length=256)
    question_2: str = Field(..., min_length=1, max_length=256)
    question_3: str = Field(..., min_length=1, max_length=256)
    answer_1: str = Field(..., min_length=1, max_length=256)
    answer_2: str = Field(..., min_length=1, max_length=256)
    answer_3: str = Field(..., min_length=1, max_length=256)


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
    """First user: username and master password."""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class SignupRequest(BaseModel):
    """New user (vault already has at least one user)."""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class ResetRequest(BaseModel):
    """Verify one user's password before wiping the vault."""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


# --- Helpers ---


def _client_ip(request: Request) -> str:
    """Client IP for rate limiting; respects X-Forwarded-For when behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _check_auth_rate_limit(request: Request) -> None:
    """Raise 429 if client has exceeded auth rate limit."""
    if not rate_limit.is_allowed(_client_ip(request), config.VAULT_RATE_LIMIT_AUTH_PER_MINUTE):
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again in a minute.",
        )


def _require_session(x_vault_session: str | None = Header(None, alias="X-Vault-Session")) -> tuple[bytes, int]:
    """Return (key, user_id) or raise 401."""
    if not x_vault_session:
        raise HTTPException(status_code=401, detail="Missing X-Vault-Session header")
    out = session_store.get_session(x_vault_session)
    if not out:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return out


def _key_for_user(conn, username: str, password: str) -> tuple[int, bytes]:
    """Return (user_id, key) for username+password. Raises ValueError if user not found or wrong password."""
    user = vault_db.get_user_by_username(conn, username)
    if not user or user["salt"] is None:
        raise ValueError("User not found")
    key = derive_key(password.encode("utf-8"), bytes(user["salt"]))
    return (user["id"], key)


# --- Routes ---


@app.get("/health")
def get_health():
    """Liveness: returns 200 if the app is running. No auth. For orchestrators and load balancers."""
    return {"status": "ok"}


@app.get("/ready")
def get_ready():
    """Readiness: returns 200 if the app can serve (DB reachable). No auth. For Kubernetes/orchestrators."""
    try:
        with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ready"}
    except Exception as e:
        _logger.warning("Ready check failed: %s", e)
        raise HTTPException(status_code=503, detail="Service not ready") from e


@app.get("/vault/status", response_model=VaultStatusResponse)
def get_vault_status():
    """Return whether the vault has been initialized (at least one user). No auth required. Used to show setup vs login."""
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        return VaultStatusResponse(initialized=vault_db.vault_initialized(conn))


@app.post("/setup", response_model=UnlockResponse)
def post_setup(request: Request, body: SetupRequest):
    """First-time setup: create first user (username + master password), return session. Fails if vault already initialized. Audit: vault_setup."""
    _check_auth_rate_limit(request)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        if vault_db.vault_initialized(conn):
            raise HTTPException(status_code=400, detail="Vault already initialized. Use Log in or Create account.")
        user_id = vault_db.init_first_user(conn, body.username.strip(), body.password)
        _, key = _key_for_user(conn, body.username.strip(), body.password)
        session_id = session_store.create_session(key, user_id)
        audit.log_event("vault_setup", resource_id=None, user_id=user_id)
        return UnlockResponse(session_id=session_id)


@app.post("/vault/reset")
def post_vault_reset(body: ResetRequest):
    """Reset vault: verify username+password for one user, then delete the database file. Next visit will show first-time setup. For testing only. Audit: vault_reset."""
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        if not vault_db.vault_initialized(conn):
            raise HTTPException(status_code=400, detail="Vault not initialized. Nothing to reset.")
        out = vault_db.verify_user_password(conn, body.username.strip(), body.password)
        if out is None:
            raise HTTPException(status_code=401, detail="Wrong username or password.")
        user_id, _ = out
        audit.log_event("vault_reset", resource_id=None, user_id=user_id)
    db_path = Path(config.VAULT_DB_PATH)
    if db_path.is_file():
        try:
            os.remove(db_path)
        except OSError as e:
            _logger.error("Failed to remove vault DB at %s: %s", db_path, e)
            raise HTTPException(status_code=500, detail="Failed to reset vault. Check logs.") from e
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
def post_unlock(request: Request, body: UnlockRequest):
    """Unlock with username + (password, recovery key, or 3 answers). Returns session id."""
    _check_auth_rate_limit(request)
    which = _unlock_which(body)
    username = body.username.strip()

    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        if not vault_db.vault_initialized(conn):
            raise HTTPException(status_code=400, detail="Vault not initialized; use setup first.")
        if which == "recovery_key":
            out = vault_db.unlock_with_recovery_key(conn, username, body.recovery_key.strip().encode("utf-8"))
            if out is None:
                raise HTTPException(status_code=400, detail="Invalid username, recovery key, or recovery not set up.")
            user_id, key = out
        elif which == "recovery_answers":
            a1, a2, a3 = body.recovery_answers[0].strip(), body.recovery_answers[1].strip(), body.recovery_answers[2].strip()
            out = vault_db.unlock_with_recovery_answers(conn, username, a1, a2, a3)
            if out is None:
                raise HTTPException(status_code=400, detail="Invalid username, answers, or recovery questions not set up.")
            user_id, key = out
        else:
            out = vault_db.verify_user_password(conn, username, body.password)
            if out is None:
                raise HTTPException(status_code=400, detail="Wrong username or password.")
            user_id, key = out
        session_id = session_store.create_session(key, user_id)
        audit.log_event(
            "unlock_recovery_answers" if which == "recovery_answers" else ("unlock_recovery" if which == "recovery_key" else "unlock"),
            resource_id=None,
            user_id=user_id,
        )
        return UnlockResponse(session_id=session_id)


@app.post("/signup", response_model=UnlockResponse)
def post_signup(request: Request, body: SignupRequest):
    """Create a new user account (vault must already be initialized). Returns session id so they are logged in. Audit: signup."""
    _check_auth_rate_limit(request)
    try:
        with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
            if not vault_db.vault_initialized(conn):
                raise HTTPException(status_code=400, detail="Vault not initialized; use setup to create first user.")
            user_id = vault_db.add_user(conn, body.username.strip(), body.password)
            _, key = _key_for_user(conn, body.username.strip(), body.password)
            session_id = session_store.create_session(key, user_id)
            audit.log_event("signup", resource_id=None, user_id=user_id)
            return UnlockResponse(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/lock")
def post_lock(x_vault_session: str | None = Header(None, alias="X-Vault-Session")):
    """Discard the session (lock). Audit: lock."""
    user_id = None
    if x_vault_session:
        out = session_store.get_session(x_vault_session)
        if out:
            user_id = out[1]
        session_store.delete_session(x_vault_session)
    audit.log_event("lock", resource_id=None, user_id=user_id)
    return Response(status_code=204)  # No Content: no body


@app.get("/folders")
def get_folders(x_vault_session: str | None = Header(None, alias="X-Vault-Session")):
    """List folders for the current user."""
    key, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        folders = vault_db.get_folders(conn, key, user_id)
        audit.log_event("list_folders", resource_id=None, user_id=user_id)
        return folders


@app.post("/folders", response_model=CreateFolderResponse)
def post_folder(
    body: CreateFolderRequest,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Create a folder. Audit: create_folder."""
    key, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        folder_id = vault_db.create_folder(conn, key, user_id, body.name.strip())
        audit.log_event("create_folder", resource_id=folder_id, user_id=user_id)
        return CreateFolderResponse(id=folder_id)


@app.get("/entries")
def get_entries(
    folder_id: int,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """List entries in a folder."""
    key, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        entries = vault_db.get_entries(conn, key, folder_id)
        audit.log_event("list_entries", resource_id=folder_id, user_id=user_id)
        return entries


@app.get("/search")
def search_entries(
    q: str = "",
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Search entries by title, username, notes, or URL (case-insensitive). Returns list of entries with folder_id and folder_name. Empty q returns []."""
    key, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        results = vault_db.search_entries(conn, key, user_id, q)
        audit.log_event("search", resource_id=None, user_id=user_id)
        return results


@app.post("/entries", response_model=CreateEntryResponse)
def post_entry(
    body: CreateEntryRequest,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Create an entry in a folder. Audit: create_entry."""
    key, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
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


@app.patch("/entries/{entry_id}")
def patch_entry(
    entry_id: int,
    body: UpdateEntryRequest,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Update an entry by id. Audit: update_entry. Returns 204 on success, 404 if not found or not owned."""
    key, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
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


@app.delete("/entries/{entry_id}")
def delete_entry_route(
    entry_id: int,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Delete an entry by id. Audit: delete_entry. Returns 204 on success, 404 if not found or not owned."""
    key, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        ok = vault_db.delete_entry(conn, entry_id, user_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Entry not found")
        audit.log_event("delete_entry", resource_id=entry_id, user_id=user_id)
        return Response(status_code=204)


@app.post("/recovery/setup", response_model=RecoverySetupResponse)
def post_recovery_setup(
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Generate and store recovery key for the current user. Returns recovery_key once; user must store it offline. Audit: recovery_setup."""
    key, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        recovery_key = vault_db.generate_and_store_recovery(conn, user_id, key)
        audit.log_event("recovery_setup", resource_id=None, user_id=user_id)
        return RecoverySetupResponse(recovery_key=recovery_key)


@app.get("/recovery/status", response_model=RecoveryStatusResponse)
def get_recovery_status(
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Return recovery config for the current user: configured, key_configured, questions_configured, and questions if applicable."""
    _, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        key_ok, qa_ok = vault_db.get_recovery_methods(conn, user_id)
        configured = key_ok or qa_ok
        questions = None
        if qa_ok:
            q1, q2, q3 = vault_db.get_recovery_questions(conn, user_id)
            questions = [q1, q2, q3]
        return RecoveryStatusResponse(
            configured=configured,
            key_configured=key_ok,
            questions_configured=qa_ok,
            questions=questions,
        )


@app.get("/recovery/questions", response_model=RecoveryQuestionsPublicResponse)
def get_recovery_questions_public(request: Request, username: str = ""):
    """Public endpoint so unlock page can show the 3 question fields for a user. No auth. Query: username. Rate limited to prevent username enumeration."""
    _check_auth_rate_limit(request)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        if not username.strip():
            return RecoveryQuestionsPublicResponse(questions_configured=False, questions=None)
        q1, q2, q3 = vault_db.get_recovery_questions_by_username(conn, username)
        qa_ok = q1 is not None
        questions = [q1, q2, q3] if qa_ok else None
        return RecoveryQuestionsPublicResponse(questions_configured=qa_ok, questions=questions)


@app.post("/recovery/setup-questions")
def post_recovery_setup_questions(
    body: RecoverySetupQuestionsRequest,
    x_vault_session: str | None = Header(None, alias="X-Vault-Session"),
):
    """Store 3 security questions for the current user. User must be unlocked. Audit: recovery_setup_questions."""
    key, user_id = _require_session(x_vault_session)
    with vault_db.db_connection(config.VAULT_DB_PATH) as conn:
        vault_db.set_recovery_questions(
            conn,
            user_id,
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
