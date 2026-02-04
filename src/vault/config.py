"""
Load configuration from environment. No secrets in code; paths and timeouts
come from env so the same image can run in dev vs prod (12-factor style).
"""

from __future__ import annotations

import os
from pathlib import Path

# DB path; default next to cwd so local dev works without setting env.
VAULT_DB_PATH: Path = Path(
    os.environ.get("VAULT_DB_PATH", "vault.db")
).resolve()

# Session timeout in minutes (inactivity); default 15 per design.
VAULT_SESSION_TIMEOUT_MINUTES: int = int(
    os.environ.get("VAULT_SESSION_TIMEOUT_MINUTES", "15")
)

# Audit log path; separate file so we never log secrets there.
VAULT_AUDIT_LOG_PATH: Path = Path(
    os.environ.get("VAULT_AUDIT_LOG_PATH", "audit.log")
).resolve()
