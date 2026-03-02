"""
Load configuration from environment. No secrets in code; paths and timeouts
come from env so the same image can run in dev vs prod (12-factor style).
Validates config at startup (e.g. in lifespan) so the app fails fast with clear errors.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# DB path; default next to cwd so local dev works without setting env.
VAULT_DB_PATH: Path = Path(
    os.environ.get("VAULT_DB_PATH", "vault.db")
).resolve()

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


# Session timeout in minutes (inactivity); default 15 per design.
VAULT_SESSION_TIMEOUT_MINUTES: int = _env_int("VAULT_SESSION_TIMEOUT_MINUTES", 15)

# Audit log path; separate file so we never log secrets there.
VAULT_AUDIT_LOG_PATH: Path = Path(
    os.environ.get("VAULT_AUDIT_LOG_PATH", "audit.log")
).resolve()

# Application log level (DEBUG, INFO, WARNING, ERROR); default INFO.
VAULT_LOG_LEVEL: str = os.environ.get("VAULT_LOG_LEVEL", "INFO").upper()

# CORS: comma-separated origins (e.g. https://app.example.com). Empty = same-origin only.
VAULT_CORS_ORIGINS: str = os.environ.get("VAULT_CORS_ORIGINS", "").strip()

# Optional Sentry DSN for error tracking. If empty, Sentry is disabled.
VAULT_SENTRY_DSN: str = os.environ.get("VAULT_SENTRY_DSN", "").strip()

# Rate limit: max auth attempts (setup/unlock/signup) per IP per minute.
VAULT_RATE_LIMIT_AUTH_PER_MINUTE: int = _env_int("VAULT_RATE_LIMIT_AUTH_PER_MINUTE", 10)

# Optional session persistence: path to directory for sessions DB. If set, VAULT_SESSION_SECRET must be set (min 32 chars).
VAULT_SESSION_STORE_PATH: str | None = os.environ.get("VAULT_SESSION_STORE_PATH", "").strip() or None
VAULT_SESSION_SECRET: str | None = os.environ.get("VAULT_SESSION_SECRET", "").strip() or None


def validate_config() -> None:
    """
    Validate configuration at startup. Exits with a clear message if invalid.
    Call once when the app starts (e.g. in lifespan or before uvicorn).
    """
    errors: list[str] = []

    if VAULT_SESSION_TIMEOUT_MINUTES < 1 or VAULT_SESSION_TIMEOUT_MINUTES > 1440:
        errors.append(
            f"VAULT_SESSION_TIMEOUT_MINUTES must be between 1 and 1440 (got {VAULT_SESSION_TIMEOUT_MINUTES})."
        )

    if VAULT_LOG_LEVEL not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        errors.append(
            f"VAULT_LOG_LEVEL must be DEBUG, INFO, WARNING, or ERROR (got {VAULT_LOG_LEVEL})."
        )

    try:
        VAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        errors.append(f"VAULT_DB_PATH parent directory not writable: {VAULT_DB_PATH.parent}: {e}")

    try:
        VAULT_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        errors.append(f"VAULT_AUDIT_LOG_PATH parent directory not writable: {VAULT_AUDIT_LOG_PATH.parent}: {e}")

    if VAULT_RATE_LIMIT_AUTH_PER_MINUTE < 1 or VAULT_RATE_LIMIT_AUTH_PER_MINUTE > 120:
        errors.append(
            f"VAULT_RATE_LIMIT_AUTH_PER_MINUTE must be between 1 and 120 (got {VAULT_RATE_LIMIT_AUTH_PER_MINUTE})."
        )

    if VAULT_SESSION_STORE_PATH is not None:
        if not VAULT_SESSION_SECRET or len(VAULT_SESSION_SECRET) < 32:
            errors.append(
                "VAULT_SESSION_STORE_PATH is set; VAULT_SESSION_SECRET must be set and at least 32 characters."
            )
        else:
            store_dir = Path(VAULT_SESSION_STORE_PATH).resolve()
            try:
                store_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(f"VAULT_SESSION_STORE_PATH directory not writable: {store_dir}: {e}")

    if errors:
        for msg in errors:
            print(f"Config error: {msg}", file=sys.stderr)
        sys.exit(1)
