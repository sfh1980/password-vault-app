"""
Session store: session_id -> key + user_id + last_activity.
In-memory by default; optional SQLite-backed persistence (encrypted) when
VAULT_SESSION_STORE_PATH and VAULT_SESSION_SECRET are set. Survives restarts when persistent.
"""

from __future__ import annotations

import base64
import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

# Session data: key (bytes), last_activity (float), user_id (int)
_sessions: dict[str, dict[str, Any]] = {}
_timeout_seconds: float = 15 * 60  # set by API on startup from config

# Optional persistent store (SQLite)
_store_conn: sqlite3.Connection | None = None
_store_key: bytes | None = None

# Salt for session store key derivation (fixed so we can decrypt after restart)
_SESSION_STORE_SALT = b"vault-session-store-v1"


def set_timeout_minutes(minutes: int) -> None:
    global _timeout_seconds
    _timeout_seconds = minutes * 60.0


def _ensure_store() -> tuple[sqlite3.Connection, bytes] | None:
    """If persistence is configured, open DB and return (conn, key). Else None."""
    global _store_conn, _store_key
    try:
        from vault import config
    except ImportError:
        return None
    if not config.VAULT_SESSION_STORE_PATH or not config.VAULT_SESSION_SECRET:
        return None
    if _store_conn is not None and _store_key is not None:
        return _store_conn, _store_key
    from vault.crypto import derive_key, decrypt, encrypt
    store_dir = Path(config.VAULT_SESSION_STORE_PATH).resolve()
    store_dir.mkdir(parents=True, exist_ok=True)
    db_path = store_dir / "sessions.db"
    _store_conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _store_conn.execute(
        "CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, payload BLOB, last_activity REAL)"
    )
    _store_conn.commit()
    _store_key = derive_key(config.VAULT_SESSION_SECRET.encode("utf-8"), _SESSION_STORE_SALT)
    return _store_conn, _store_key


def _persist_save(session_id: str, key: bytes, user_id: int) -> None:
    store = _ensure_store()
    if not store:
        return
    conn, key_enc = store
    payload = json.dumps({"key_b64": base64.b64encode(key).decode(), "user_id": user_id}).encode("utf-8")
    from vault.crypto import encrypt
    blob = encrypt(key_enc, payload)
    now = time.monotonic()
    conn.execute(
        "INSERT OR REPLACE INTO sessions (session_id, payload, last_activity) VALUES (?, ?, ?)",
        (session_id, blob, now),
    )
    conn.commit()


def _persist_load(session_id: str) -> dict[str, Any] | None:
    store = _ensure_store()
    if not store:
        return None
    conn, key_enc = store
    row = conn.execute(
        "SELECT payload, last_activity FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if not row:
        return None
    from vault.crypto import decrypt
    try:
        payload = json.loads(decrypt(key_enc, row[0]).decode("utf-8"))
        payload["key"] = base64.b64decode(payload["key_b64"])
        payload["last_activity"] = row[1]
        return payload
    except (sqlite3.Error, json.JSONDecodeError, ValueError, KeyError):
        return None


def _persist_update_activity(session_id: str, last_activity: float) -> None:
    store = _ensure_store()
    if not store:
        return
    conn, _ = store
    conn.execute("UPDATE sessions SET last_activity = ? WHERE session_id = ?", (last_activity, session_id))
    conn.commit()


def _persist_delete(session_id: str) -> None:
    store = _ensure_store()
    if not store:
        return
    conn, _ = store
    conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    conn.commit()


def create_session(key: bytes, user_id: int = 1) -> str:
    """Store key and user_id under a new session id; return the session id."""
    sid = secrets.token_urlsafe(32)
    now = time.monotonic()
    _sessions[sid] = {
        "key": key,
        "last_activity": now,
        "user_id": user_id,
    }
    _persist_save(sid, key, user_id)
    return sid


def get_session(session_id: str) -> tuple[bytes, int] | None:
    """
    Return (key, user_id) if the session exists and has not timed out.
    Update last_activity. Return None if missing or expired.
    """
    if not session_id:
        return None
    now = time.monotonic()
    # Memory first
    data = _sessions.get(session_id)
    if data is None:
        # Try persistent store
        data = _persist_load(session_id)
        if data is None:
            return None
        if now - data["last_activity"] > _timeout_seconds:
            _persist_delete(session_id)
            return None
        # Restore to memory and update activity
        data["last_activity"] = now
        _sessions[session_id] = data
        _persist_update_activity(session_id, now)
        return (data["key"], data["user_id"])
    if now - data["last_activity"] > _timeout_seconds:
        del _sessions[session_id]
        _persist_delete(session_id)
        return None
    data["last_activity"] = now
    _persist_update_activity(session_id, now)
    return (data["key"], data["user_id"])


def delete_session(session_id: str) -> None:
    """Remove the session (lock)."""
    _sessions.pop(session_id, None)
    _persist_delete(session_id)
