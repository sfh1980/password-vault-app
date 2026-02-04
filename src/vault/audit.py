"""
Audit log: record who did what when. No secrets—only event type, resource id,
optional user id, and timestamp. Single place for all audit events so we never
leak credentials in logs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path


def log_event(
    event_type: str,
    resource_id: str | int | None = None,
    user_id: int | None = None,
    log_path: Path | None = None,
) -> None:
    """
    Append one audit line. Call after every sensitive action (unlock, lock,
    view entry, copy password, create/update/delete). Never pass passwords or keys.

    Format: ISO8601 timestamp, event_type, resource_id, user_id (tab-separated).
    """
    path = log_path or _default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat(timespec="seconds")
    parts = [ts, event_type, str(resource_id) if resource_id is not None else "", str(user_id) if user_id is not None else ""]
    line = "\t".join(parts) + "\n"
    with path.open("a") as f:
        f.write(line)


def _default_log_path() -> Path:
    from vault.config import VAULT_AUDIT_LOG_PATH
    return VAULT_AUDIT_LOG_PATH
