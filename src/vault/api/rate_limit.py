"""
Simple in-memory rate limiter for auth endpoints (setup, unlock, signup).
Limits requests per client IP per minute. Prunes old entries on each check.
"""

from __future__ import annotations

import time
from collections import defaultdict

# IP -> list of timestamps (last N seconds)
_attempts: dict[str, list[float]] = defaultdict(list)
_window_seconds = 60.0


def set_window_seconds(seconds: float) -> None:
    global _window_seconds
    _window_seconds = seconds


def is_allowed(client_ip: str, max_per_minute: int) -> bool:
    """
    Return True if this IP is under the limit, False if rate limited.
    Call before processing auth request; prune old entries.
    """
    now = time.monotonic()
    cutoff = now - _window_seconds
    _attempts[client_ip] = [t for t in _attempts[client_ip] if t > cutoff]
    if len(_attempts[client_ip]) >= max_per_minute:
        return False
    _attempts[client_ip].append(now)
    return True
