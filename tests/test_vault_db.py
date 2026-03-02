"""
Tests for vault_db (migrations, salt, create_folder, create_entry, get_folders, get_entries).
Uses a temporary DB; no production data. Run with: pytest tests/ -v
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Isolate DB path before importing vault (config reads env at import).
_test_dir = tempfile.mkdtemp(prefix="vault_db_test_")
os.environ["VAULT_DB_PATH"] = os.path.join(_test_dir, "vault.db")

from vault import vault_db
from vault.crypto import derive_key, encrypt, random_bytes

# Use a fixed password for key derivation in tests; salt comes from inited DB.
TEST_PASSWORD = b"test-db-password"


@pytest.fixture
def conn():
    """Open a fresh test DB; run migrations; yield connection; close."""
    path = os.environ["VAULT_DB_PATH"]
    c = vault_db.open_db(path)
    try:
        yield c
    finally:
        c.close()


@pytest.fixture
def inited_conn(conn):
    """DB with salt and one user; yields (conn, key, user_id)."""
    if vault_db.get_salt(conn) is None:
        salt = vault_db.init_salt(conn)
    else:
        row = conn.execute("SELECT salt FROM vault_meta WHERE id = 1").fetchone()
        salt = bytes(row[0])
    key = derive_key(TEST_PASSWORD, salt)
    user_id = vault_db.get_or_create_first_user(conn)
    return conn, key, user_id


def test_migrations_run_and_schema_version_set(conn):
    """After open_db, schema_version table exists and version is at least 1."""
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    assert row is not None
    assert row[0] >= 1


def test_init_salt_stores_salt(conn):
    """init_salt stores a 16-byte salt and get_salt returns it."""
    salt = vault_db.init_salt(conn)
    assert isinstance(salt, bytes)
    assert len(salt) == 16
    assert vault_db.get_salt(conn) == salt


def test_create_folder_returns_id_and_get_folders_includes_it(inited_conn):
    """create_folder returns new id; get_folders returns the folder with decrypted name."""
    conn, key, user_id = inited_conn
    folder_id = vault_db.create_folder(conn, key, user_id, "My Folder")
    assert isinstance(folder_id, int)
    assert folder_id >= 1
    folders = vault_db.get_folders(conn, key, user_id)
    assert len(folders) == 1
    assert folders[0]["id"] == folder_id
    assert folders[0]["name"] == "My Folder"


def test_create_entry_returns_id_and_get_entries_decrypts(inited_conn):
    """create_entry stores encrypted data; get_entries returns decrypted fields."""
    conn, key, user_id = inited_conn
    folder_id = vault_db.create_folder(conn, key, user_id, "F")
    entry_id = vault_db.create_entry(
        conn, key, folder_id,
        title="Entry Title",
        username="user",
        password="pass",
        url="https://x.com",
        notes="Note",
    )
    assert isinstance(entry_id, int)
    entries = vault_db.get_entries(conn, key, folder_id)
    assert len(entries) == 1
    assert entries[0]["id"] == entry_id
    assert entries[0]["title"] == "Entry Title"
    assert entries[0]["username"] == "user"
    assert entries[0]["password"] == "pass"
    assert entries[0]["url"] == "https://x.com"
    assert entries[0]["notes"] == "Note"


def test_update_entry_partial_and_get_entry(inited_conn):
    """update_entry updates only provided fields; get_entry returns updated data."""
    conn, key, user_id = inited_conn
    folder_id = vault_db.create_folder(conn, key, user_id, "F")
    entry_id = vault_db.create_entry(
        conn, key, folder_id, title="Old", username="u", password="p", notes="n", url=""
    )
    ok = vault_db.update_entry(conn, key, entry_id, user_id, title="New Title", notes="New notes")
    assert ok is True
    entry = vault_db.get_entry(conn, key, entry_id, user_id)
    assert entry is not None
    assert entry["title"] == "New Title"
    assert entry["notes"] == "New notes"
    assert entry["username"] == "u"
    assert entry["password"] == "p"


def test_delete_entry_removes_and_get_entry_returns_none(inited_conn):
    """delete_entry removes the entry; get_entry returns None."""
    conn, key, user_id = inited_conn
    folder_id = vault_db.create_folder(conn, key, user_id, "F")
    entry_id = vault_db.create_entry(conn, key, folder_id, title="X", username="", password="", notes="", url="")
    ok = vault_db.delete_entry(conn, entry_id, user_id)
    assert ok is True
    assert vault_db.get_entry(conn, key, entry_id, user_id) is None
    assert len(vault_db.get_entries(conn, key, folder_id)) == 0


def test_search_entries_returns_matches_with_folder_name(inited_conn):
    """search_entries returns entries matching q in title/username/notes/url; includes folder_name."""
    conn, key, user_id = inited_conn
    folder_id = vault_db.create_folder(conn, key, user_id, "MyFolder")
    vault_db.create_entry(
        conn, key, folder_id,
        title="Work Login",
        username="alice",
        password="p",
        notes="work stuff",
        url="https://work.com",
    )
    results = vault_db.search_entries(conn, key, user_id, "Work")
    assert len(results) == 1
    assert results[0]["title"] == "Work Login"
    assert results[0]["folder_name"] == "MyFolder"
    assert results[0]["folder_id"] == folder_id
    assert vault_db.search_entries(conn, key, user_id, "alice")[0]["username"] == "alice"
    assert vault_db.search_entries(conn, key, user_id, "") == []


def test_recovery_configured_false_until_set_recovery(inited_conn):
    """get_recovery_configured is False until set_recovery is called."""
    conn, key, user_id = inited_conn
    assert vault_db.get_recovery_configured(conn) is False
    recovery_salt = random_bytes(16)
    recovery_derived = derive_key(b"my-recovery-key", recovery_salt)
    wrapped = encrypt(recovery_derived, key)
    vault_db.set_recovery(conn, recovery_salt, wrapped)
    assert vault_db.get_recovery_configured(conn) is True


def test_unlock_with_recovery_key_returns_master_key(inited_conn):
    """After set_recovery, unlock_with_recovery_key returns the same master key."""
    conn, key, user_id = inited_conn
    recovery_key_bytes = b"test-recovery-key-123"
    recovery_salt = random_bytes(16)
    recovery_derived = derive_key(recovery_key_bytes, recovery_salt)
    wrapped = encrypt(recovery_derived, key)
    vault_db.set_recovery(conn, recovery_salt, wrapped)
    unwrapped = vault_db.unlock_with_recovery_key(conn, recovery_key_bytes)
    assert unwrapped is not None
    assert unwrapped == key


def test_unlock_with_recovery_key_wrong_key_returns_none(inited_conn):
    """unlock_with_recovery_key with wrong key returns None."""
    conn, key, user_id = inited_conn
    recovery_salt = random_bytes(16)
    recovery_derived = derive_key(b"correct-key", recovery_salt)
    wrapped = encrypt(recovery_derived, key)
    vault_db.set_recovery(conn, recovery_salt, wrapped)
    assert vault_db.unlock_with_recovery_key(conn, b"wrong-key") is None
