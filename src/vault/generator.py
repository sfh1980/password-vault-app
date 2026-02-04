"""
Password generator: configurable length and character set. Used by the API
and later by the web UI so all clients get the same rules (e.g. per-site presets in Phase 6+).
"""

from __future__ import annotations

import secrets
import string


def generate_password(
    length: int = 20,
    *,
    upper: bool = True,
    lower: bool = True,
    digits: bool = True,
    symbols: bool = True,
) -> str:
    """
    Return a cryptographically random password with the requested character set.

    Uses secrets.SystemRandom so the result is suitable for security-sensitive use.
    At least one character set must be enabled; otherwise length is ignored and we use defaults.
    """
    pool: list[str] = []
    if upper:
        pool.append(string.ascii_uppercase)
    if lower:
        pool.append(string.ascii_lowercase)
    if digits:
        pool.append(string.digits)
    if symbols:
        pool.append("!@#$%^&*()_+-=[]{}|;:,.<>?")
    if not pool:
        pool = [string.ascii_letters + string.digits]
    alphabet = "".join(pool)
    return "".join(secrets.choice(alphabet) for _ in range(length))
