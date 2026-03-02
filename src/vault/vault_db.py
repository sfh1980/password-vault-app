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
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag

from vault.crypto import (
    ARGON2_SALT_LEN,
    decrypt,
    derive_key,
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


@contextmanager
def db_connection(path: str | Path):
    """Context manager: open DB, yield connection, close on exit. Use in API routes."""
    conn = open_db(path)
    try:
        yield conn
    finally:
        conn.close()


def get_salt(conn: sqlite3.Connection) -> bytes | None:
    """Return the vault salt if the vault has been initialized, else None. Deprecated for new code; use vault_initialized and per-user auth."""
    row = conn.execute("SELECT salt FROM vault_meta WHERE id = 1").fetchone()
    if row and row[0] is not None:
        return bytes(row[0])
    return None


def vault_initialized(conn: sqlite3.Connection) -> bool:
    """True if at least one user exists (vault has been set up)."""
    row = conn.execute("SELECT 1 FROM users WHERE username IS NOT NULL LIMIT 1").fetchone()
    return row is not None


def init_first_user(conn: sqlite3.Connection, username: str, password: str) -> int:
    """Create the first user (vault setup). Fails if any user already exists. Returns user_id."""
    if vault_initialized(conn):
        raise ValueError("Vault already initialized")
    return _insert_user(conn, username.strip(), password)


def add_user(conn: sqlite3.Connection, username: str, password: str) -> int:
    """Create a new user (sign up). Username must be unique. Returns user_id."""
    if not vault_initialized(conn):
        raise ValueError("Vault not initialized; use setup to create first user")
    return _insert_user(conn, username.strip(), password)


def _insert_user(conn: sqlite3.Connection, username: str, password: str) -> int:
    """Insert user with username, salt, password_check_encrypted. Returns user_id."""
    if not username:
        raise ValueError("Username required")
    salt = random_bytes(ARGON2_SALT_LEN)
    key = derive_key(password.encode("utf-8"), salt)
    blob = encrypt(key, b"ok")
    cur = conn.execute(
        """INSERT INTO users (username, salt, password_check_encrypted, created_at)
           VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))""",
        (username, salt, blob),
    )
    conn.commit()
    return cur.lastrowid


def get_user_by_username(conn: sqlite3.Connection, username: str) -> dict[str, Any] | None:
    """Return user row (id, username, salt, password_check_encrypted) or None."""
    row = conn.execute(
        "SELECT id, username, salt, password_check_encrypted FROM users WHERE username = ?",
        (username.strip(),),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def verify_user_password(conn: sqlite3.Connection, username: str, password: str) -> tuple[int, bytes] | None:
    """Verify username+password; return (user_id, key) or None."""
    user = get_user_by_username(conn, username)
    if not user or user["salt"] is None or user["password_check_encrypted"] is None:
        return None
    key = derive_key(password.encode("utf-8"), bytes(user["salt"]))
    try:
        if decrypt(key, bytes(user["password_check_encrypted"])) != b"ok":
            return None
    except InvalidTag:
        return None
    return (user["id"], key)


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


def set_password_check(conn: sqlite3.Connection, key: bytes) -> None:
    """Store an encrypted blob so we can verify the master password later (e.g. on reset). Call after init_salt."""
    blob = encrypt(key, b"ok")
    conn.execute(
        "UPDATE vault_meta SET password_check_encrypted = ? WHERE id = 1",
        (blob,),
    )
    conn.commit()


def verify_password_check(conn: sqlite3.Connection, key: bytes) -> bool | None:
    """Return True if key is correct, False if wrong, None if no check blob (pre-migration vault)."""
    row = conn.execute(
        "SELECT password_check_encrypted FROM vault_meta WHERE id = 1"
    ).fetchone()
    if not row or row[0] is None:
        return None
    try:
        return decrypt(key, bytes(row[0])) == b"ok"
    except InvalidTag:
        return False


# --- Recovery (per-user; unlock when master password is forgotten) ---


def get_recovery_configured(conn: sqlite3.Connection, user_id: int) -> bool:
    """True if this user has any recovery method set (key and/or questions)."""
    row = conn.execute(
        """SELECT recovery_salt, wrapped_master_key, recovery_qa_salt, recovery_qa_wrapped
           FROM users WHERE id = ?""",
        (user_id,),
    ).fetchone()
    if not row:
        return False
    key_ok = row[0] is not None and row[1] is not None
    qa_ok = row[2] is not None and row[3] is not None
    return key_ok or qa_ok


def get_recovery_methods(conn: sqlite3.Connection, user_id: int) -> tuple[bool, bool]:
    """Return (key_configured, questions_configured) for this user."""
    row = conn.execute(
        "SELECT recovery_salt, wrapped_master_key, recovery_qa_salt, recovery_qa_wrapped FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return (False, False)
    key_ok = row[0] is not None and row[1] is not None
    qa_ok = row[2] is not None and row[3] is not None
    return (key_ok, qa_ok)


def get_recovery_questions(conn: sqlite3.Connection, user_id: int) -> tuple[str | None, str | None, str | None]:
    """Return (q1, q2, q3) if this user has questions recovery; else (None, None, None)."""
    row = conn.execute(
        "SELECT recovery_question_1, recovery_question_2, recovery_question_3 FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row or row[0] is None:
        return (None, None, None)
    return (str(row[0]), str(row[1]), str(row[2]))


def get_recovery_questions_by_username(conn: sqlite3.Connection, username: str) -> tuple[str | None, str | None, str | None]:
    """Return (q1, q2, q3) for the user with this username; else (None, None, None). No auth; used on unlock page."""
    user = get_user_by_username(conn, username.strip())
    if not user:
        return (None, None, None)
    return get_recovery_questions(conn, user["id"])


def set_recovery(
    conn: sqlite3.Connection,
    user_id: int,
    recovery_salt: bytes,
    wrapped_master_key: bytes,
) -> None:
    """Store recovery salt and wrapped master key for this user."""
    conn.execute(
        "UPDATE users SET recovery_salt = ?, wrapped_master_key = ? WHERE id = ?",
        (recovery_salt, wrapped_master_key, user_id),
    )
    conn.commit()


def generate_and_store_recovery(
    conn: sqlite3.Connection, user_id: int, master_key: bytes
) -> str:
    """
    Generate a recovery key, derive from it, wrap master key, store for user.
    Returns the recovery key string (show once to user). Used by API.
    """
    recovery_key = secrets.token_hex(32)
    recovery_salt = random_bytes(ARGON2_SALT_LEN)
    recovery_derived = derive_key(recovery_key.encode("utf-8"), recovery_salt)
    wrapped = encrypt(recovery_derived, master_key)
    set_recovery(conn, user_id, recovery_salt, wrapped)
    return recovery_key


def get_recovery_material(conn: sqlite3.Connection, user_id: int) -> tuple[bytes | None, bytes | None]:
    """Return (recovery_salt, wrapped_master_key) for this user or (None, None)."""
    row = conn.execute(
        "SELECT recovery_salt, wrapped_master_key FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row or row[0] is None or row[1] is None:
        return (None, None)
    return (bytes(row[0]), bytes(row[1]))


def unlock_with_recovery_key(
    conn: sqlite3.Connection, username: str, recovery_key_bytes: bytes
) -> tuple[int, bytes] | None:
    """
    Unlock user by username and recovery key. Returns (user_id, master_key) or None.
    """
    user = get_user_by_username(conn, username.strip())
    if not user:
        return None
    recovery_salt, wrapped = get_recovery_material(conn, user["id"])
    if recovery_salt is None or wrapped is None:
        return None
    try:
        recovery_derived = derive_key(recovery_key_bytes, recovery_salt)
        master_key = decrypt(recovery_derived, wrapped)
        return (user["id"], master_key)
    except InvalidTag:
        return None


# Delimiter for combining 3 answers into one key material (must not appear in normal answers).
_QA_DELIM = "\x00"


def set_recovery_questions(
    conn: sqlite3.Connection,
    user_id: int,
    master_key: bytes,
    question_1: str,
    question_2: str,
    question_3: str,
    answer_1: str,
    answer_2: str,
    answer_3: str,
) -> None:
    """Store 3 questions and wrapped master key for this user."""
    qa_salt = random_bytes(ARGON2_SALT_LEN)
    key_material = (answer_1 + _QA_DELIM + answer_2 + _QA_DELIM + answer_3).encode("utf-8")
    derived = derive_key(key_material, qa_salt)
    wrapped = encrypt(derived, master_key)
    conn.execute(
        """UPDATE users SET
           recovery_qa_salt = ?, recovery_qa_wrapped = ?,
           recovery_question_1 = ?, recovery_question_2 = ?, recovery_question_3 = ?
           WHERE id = ?""",
        (qa_salt, wrapped, question_1.strip(), question_2.strip(), question_3.strip(), user_id),
    )
    conn.commit()


def get_qa_recovery_material(conn: sqlite3.Connection, user_id: int) -> tuple[bytes | None, bytes | None]:
    """Return (recovery_qa_salt, recovery_qa_wrapped) for this user or (None, None)."""
    row = conn.execute(
        "SELECT recovery_qa_salt, recovery_qa_wrapped FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row or row[0] is None or row[1] is None:
        return (None, None)
    return (bytes(row[0]), bytes(row[1]))


def unlock_with_recovery_answers(
    conn: sqlite3.Connection, username: str, answer_1: str, answer_2: str, answer_3: str
) -> tuple[int, bytes] | None:
    """Unlock user by username and 3 answers. Returns (user_id, master_key) or None."""
    user = get_user_by_username(conn, username.strip())
    if not user:
        return None
    qa_salt, wrapped = get_qa_recovery_material(conn, user["id"])
    if qa_salt is None or wrapped is None:
        return None
    try:
        key_material = (answer_1 + _QA_DELIM + answer_2 + _QA_DELIM + answer_3).encode("utf-8")
        derived = derive_key(key_material, qa_salt)
        master_key = decrypt(derived, wrapped)
        return (user["id"], master_key)
    except InvalidTag:
        return None


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


def _entry_owned_by_user(conn: sqlite3.Connection, entry_id: int, user_id: int) -> bool:
    """True if entry exists and its folder belongs to user."""
    row = conn.execute(
        """SELECT 1 FROM entries e
           INNER JOIN folders f ON e.folder_id = f.id
           WHERE e.id = ? AND f.user_id = ?""",
        (entry_id, user_id),
    ).fetchone()
    return row is not None


def get_entry(
    conn: sqlite3.Connection, key: bytes, entry_id: int, user_id: int
) -> dict[str, Any] | None:
    """Return one entry by id if it exists and its folder belongs to user; else None."""
    row = conn.execute(
        """SELECT e.id, e.folder_id, e.title_encrypted, e.username_encrypted,
                  e.password_encrypted, e.notes_encrypted, e.url_encrypted, e.created_at
           FROM entries e
           INNER JOIN folders f ON e.folder_id = f.id
           WHERE e.id = ? AND f.user_id = ?""",
        (entry_id, user_id),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "folder_id": row["folder_id"],
        "title": _decrypt_field(key, row["title_encrypted"]),
        "username": _decrypt_field(key, row["username_encrypted"]),
        "password": _decrypt_field(key, row["password_encrypted"]),
        "notes": _decrypt_field(key, row["notes_encrypted"]),
        "url": _decrypt_field(key, row["url_encrypted"]),
        "created_at": row["created_at"],
    }


def update_entry(
    conn: sqlite3.Connection,
    key: bytes,
    entry_id: int,
    user_id: int,
    *,
    title: str | None = None,
    username: str | None = None,
    password: str | None = None,
    notes: str | None = None,
    url: str | None = None,
) -> bool:
    """Update entry by id; only provided fields are updated. Returns True if updated, False if not found/not owned."""
    if not _entry_owned_by_user(conn, entry_id, user_id):
        return False
    existing = get_entry(conn, key, entry_id, user_id)
    if not existing:
        return False
    new_title = title if title is not None else existing["title"]
    new_username = username if username is not None else existing["username"]
    new_password = password if password is not None else existing["password"]
    new_notes = notes if notes is not None else existing["notes"]
    new_url = url if url is not None else existing["url"]

    title_blob = _encrypt_field(key, new_title) or encrypt(key, b"")
    username_blob = _encrypt_field(key, new_username)
    password_blob = _encrypt_field(key, new_password) or encrypt(key, b"")
    notes_blob = _encrypt_field(key, new_notes)
    url_blob = _encrypt_field(key, new_url)

    conn.execute(
        """UPDATE entries SET
           title_encrypted = ?, username_encrypted = ?, password_encrypted = ?,
           notes_encrypted = ?, url_encrypted = ?
           WHERE id = ?""",
        (title_blob, username_blob, password_blob, notes_blob, url_blob, entry_id),
    )
    conn.commit()
    return True


def delete_entry(conn: sqlite3.Connection, entry_id: int, user_id: int) -> bool:
    """Delete entry by id if it belongs to user (via folder). Returns True if deleted."""
    cur = conn.execute(
        """DELETE FROM entries WHERE id = ?
           AND folder_id IN (SELECT id FROM folders WHERE user_id = ?)""",
        (entry_id, user_id),
    )
    conn.commit()
    return cur.rowcount == 1


def search_entries(
    conn: sqlite3.Connection, key: bytes, user_id: int, q: str
) -> list[dict[str, Any]]:
    """Search entries in user's folders. q is matched (case-insensitive) against title, username, notes, url. Returns list of entries with folder_id and folder_name added. Empty q returns []."""
    q_clean = q.strip().lower()
    if not q_clean:
        return []
    folders = get_folders(conn, key, user_id)
    results: list[dict[str, Any]] = []
    for folder in folders:
        entries = get_entries(conn, key, folder["id"])
        for entry in entries:
            if (
                q_clean in (entry.get("title") or "").lower()
                or q_clean in (entry.get("username") or "").lower()
                or q_clean in (entry.get("notes") or "").lower()
                or q_clean in (entry.get("url") or "").lower()
            ):
                out = dict(entry)
                out["folder_id"] = folder["id"]
                out["folder_name"] = folder["name"]
                results.append(out)
    return results
