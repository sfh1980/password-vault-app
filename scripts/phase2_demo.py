#!/usr/bin/env python3
"""
Phase 2 demo: create a user, folder, and one entry (encrypted), then read it back.

Run from project root with venv active:
  python scripts/phase2_demo.py

Or: python -m scripts.phase2_demo  (if src is on path and scripts is a package)
Simpler: from project root, PYTHONPATH=src python scripts/phase2_demo.py
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

# Project root = parent of scripts/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vault.crypto import derive_key
from vault import vault_db

DB_PATH = ROOT / "demo_vault.db"


def main() -> None:
    password = getpass.getpass("Master password: ").encode("utf-8")
    if not password:
        print("Password cannot be empty.")
        sys.exit(1)

    conn = vault_db.open_db(DB_PATH)
    try:
        salt = vault_db.get_salt(conn)
        if salt is None:
            salt = vault_db.init_salt(conn)
            print("New vault: stored salt.")
        key = derive_key(password, salt)

        user_id = vault_db.create_user(conn)
        folder_id = vault_db.create_folder(conn, key, user_id, "Personal")
        entry_id = vault_db.create_entry(
            conn,
            key,
            folder_id,
            title="Test login",
            username="demo@example.com",
            password="super-secret",
            url="https://example.com",
            notes="Phase 2 demo entry",
        )
        print(f"Created user {user_id}, folder {folder_id}, entry {entry_id}.")

        folders = vault_db.get_folders(conn, key, user_id)
        entries = vault_db.get_entries(conn, key, folder_id)
        assert folders, "No folders?"
        assert entries, "No entries?"
        entry = entries[0]
        print(
            f"Read back: title={entry['title']!r}, username={entry['username']!r}, "
            f"password={entry['password']!r}, url={entry['url']!r}."
        )
        if (
            entry["title"] == "Test login"
            and entry["password"] == "super-secret"
        ):
            print("Phase 2 demo OK: encrypted storage and read-back verified.")
        else:
            print("Mismatch.")
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
