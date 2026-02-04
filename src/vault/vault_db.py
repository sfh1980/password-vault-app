"""
SQLite persistence with application-level encryption. All sensitive columns
are stored as ciphertext (BLOB); the key is passed in by the caller and
never stored. Separation of concerns: only this module touches the DB schema
and SQL; API/CLI call here, never raw SQL elsewhere.

- Migrations: ordered SQL files in migrations/; schema_version tracks applied.
- Encrypt per field so we can query by id/folder_id/created_at without the key.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from vault.crypto import (
    ARGON2_SALT_LEN,
    decrypt,
    encrypt,
    random_bytes,
)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


def _encrypt_field(key: bytes, value: str) -> bytes | None:
    """Encode str to UTF-8, encrypt; return None for empty string (store as NULL)."""
    if not value:
        return None
    return encrypt(key, value.encode("utf-8"))


def _decrypt_field(key: bytes, blob: bytes | None) -> str:
    """Decrypt BLOB to str; return '' for NULL."""
    if blob is None:
        return ""
    return decrypt(key, blob).decode("utf-8")


def _run_migrations(conn: sqlite3.Connection) -> None:
    """
    Run migration files 001_*.sql, 002_*.sql in order. schema_version holds
    the last applied version so we can add new migrations without re-running old ones.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
    )
    conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (0)")
    conn.commit()

    row = conn.execute("SELECT version FROM schema_version").fetchone()
    current = row[0] if row else 0

    pattern = re.compile(r"^(\d+)_")
    migration_files = sorted(
        (f for f in MIGRATIONS_DIR.glob("*.sql") if pattern.match(f.name)),
        key=lambda f: int(pattern.match(f.name).group(1)),
    )
    for path in migration_files:
        n = int(pattern.match(path.name).group(1))
        if n <= current:
            continue
        sql = path.read_text()
        conn.executescript(sql)
        conn.commit()


def open_db(path: str | Path) -> sqlite3.Connection:
    """
    Open or create the vault DB and run pending migrations. Caller must close
    the connection when done.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _run_migrations(conn)
    return conn


def get_salt(conn: sqlite3.Connection) -> bytes | None:
    """Return the vault salt if the vault has been initialized, else None."""
    row = conn.execute("SELECT salt FROM vault_meta WHERE id = 1").fetchone()
    if row and row[0] is not None:
        return bytes(row[0])
    return None


def init_salt(conn: sqlite3.Connection) -> bytes:
    """
    Generate and store a new vault salt. Call only once when creating a new vault.
    Returns the salt so the caller can derive_key(password, salt).
    """
    salt = random_bytes(ARGON2_SALT_LEN)
    conn.execute(
        "INSERT OR REPLACE INTO vault_meta (id, salt) VALUES (1, ?)",
        (salt,),
    )
    conn.commit()
    return salt


def create_user(conn: sqlite3.Connection) -> int:
    """Insert a user row; returns the new user id."""
    cur = conn.execute(
        "INSERT INTO users (created_at) VALUES (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"
    )
    conn.commit()
    return cur.lastrowid


def get_or_create_first_user(conn: sqlite3.Connection) -> int:
    """Return the first user's id; create a user if none exist (e.g. first API unlock)."""
    row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    if row:
        return row["id"]
    return create_user(conn)


def create_folder(
    conn: sqlite3.Connection,
    key: bytes,
    user_id: int,
    name: str,
) -> int:
    """Encrypt folder name and insert; returns folder id."""
    name_blob = _encrypt_field(key, name) or encrypt(key, b"")
    cur = conn.execute(
        "INSERT INTO folders (user_id, name_encrypted, created_at) VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
        (user_id, name_blob),
    )
    conn.commit()
    return cur.lastrowid


def create_entry(
    conn: sqlite3.Connection,
    key: bytes,
    folder_id: int,
    *,
    title: str,
    username: str = "",
    password: str = "",
    notes: str = "",
    url: str = "",
) -> int:
    """Encrypt entry fields and insert; returns entry id."""
    title_blob = _encrypt_field(key, title) or encrypt(key, b"")
    username_blob = _encrypt_field(key, username)
    password_blob = _encrypt_field(key, password) or encrypt(key, b"")
    notes_blob = _encrypt_field(key, notes)
    url_blob = _encrypt_field(key, url)
    cur = conn.execute(
        """INSERT INTO entries (
            folder_id, title_encrypted, username_encrypted, password_encrypted,
            notes_encrypted, url_encrypted, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
        (
            folder_id,
            title_blob,
            username_blob,
            password_blob,
            notes_blob,
            url_blob,
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_folders(conn: sqlite3.Connection, key: bytes, user_id: int) -> list[dict[str, Any]]:
    """Return folders for the user; names decrypted."""
    rows = conn.execute(
        "SELECT id, name_encrypted, created_at FROM folders WHERE user_id = ? ORDER BY id",
        (user_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "name": _decrypt_field(key, r["name_encrypted"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_entries(conn: sqlite3.Connection, key: bytes, folder_id: int) -> list[dict[str, Any]]:
    """Return entries for the folder; sensitive fields decrypted."""
    rows = conn.execute(
        """SELECT id, title_encrypted, username_encrypted, password_encrypted,
                  notes_encrypted, url_encrypted, created_at
           FROM entries WHERE folder_id = ? ORDER BY id""",
        (folder_id,),
    ).fetchall()
    return [
        {
            "id": r["id"],
            "title": _decrypt_field(key, r["title_encrypted"]),
            "username": _decrypt_field(key, r["username_encrypted"]),
            "password": _decrypt_field(key, r["password_encrypted"]),
            "notes": _decrypt_field(key, r["notes_encrypted"]),
            "url": _decrypt_field(key, r["url_encrypted"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
