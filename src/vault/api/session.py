"""
In-memory session store: session_id -> key + last_activity. The key never leaves
the server; client only holds the session id (cookie or header). Timeout
enforced on each request so we lock after N minutes of inactivity.
"""

from __future__ import annotations

import secrets
import time
from typing import Any

# Session data: key (bytes), last_activity (float), user_id (int)
_sessions: dict[str, dict[str, Any]] = {}
_timeout_seconds: float = 15 * 60  # set by API on startup from config


def set_timeout_minutes(minutes: int) -> None:
    global _timeout_seconds
    _timeout_seconds = minutes * 60.0


def create_session(key: bytes, user_id: int = 1) -> str:
    """Store key and user_id under a new session id; return the session id."""
    sid = secrets.token_urlsafe(32)
    _sessions[sid] = {
        "key": key,
        "last_activity": time.monotonic(),
        "user_id": user_id,
    }
    return sid


def get_session(session_id: str) -> tuple[bytes, int] | None:
    """
    Return (key, user_id) if the session exists and has not timed out.
    Update last_activity. Return None if missing or expired.
    """
    if not session_id:
        return None
    data = _sessions.get(session_id)
    if not data:
        return None
    now = time.monotonic()
    if now - data["last_activity"] > _timeout_seconds:
        del _sessions[session_id]
        return None
    data["last_activity"] = now
    return (data["key"], data["user_id"])


def delete_session(session_id: str) -> None:
    """Remove the session (lock)."""
    _sessions.pop(session_id, None)
