"""
Phase 1: round-trip demo. Prompts for master password, encrypts a blob to a file,
reads it back, decrypts, and verifies. No secrets kept in memory longer than needed.

Run from project root (after pip install -e .): python -m vault.cli
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

from vault.crypto import (
    AESGCM_NONCE_LEN,
    ARGON2_SALT_LEN,
    constant_time_equals,
    decrypt,
    derive_key,
    encrypt,
    random_bytes,
)

# Demo blob (in Phase 2 this becomes real vault content).
DEMO_BLOB = b'{"entries":[]}'
# Write demo file in project root (parent of src/ when run in editable install).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_FILE = _PROJECT_ROOT / "demo_vault.blob"


def _round_trip() -> None:
    password = getpass.getpass("Master password: ").encode("utf-8")
    if not password:
        print("Password cannot be empty.")
        sys.exit(1)

    # 1) Derive key from password + new random salt. Salt is stored with the file so we can decrypt later.
    salt = random_bytes(ARGON2_SALT_LEN)
    key = derive_key(password, salt)

    # 2) Encrypt: one blob, one nonce (inside encrypt()). File format: salt || nonce || ciphertext+tag.
    ciphertext = encrypt(key, DEMO_BLOB)
    blob_to_write = salt + ciphertext
    DEMO_FILE.write_bytes(blob_to_write)
    print(f"Wrote encrypted blob to {DEMO_FILE}")

    # 3) Read back and decrypt. Same password + stored salt → same key.
    key2 = derive_key(password, salt)
    read_back = DEMO_FILE.read_bytes()
    salt_back = read_back[:ARGON2_SALT_LEN]
    nonce_and_ct = read_back[ARGON2_SALT_LEN:]

    if not constant_time_equals(salt, salt_back):
        print("Salt mismatch (file tampered?).")
        sys.exit(1)
    plaintext = decrypt(key2, nonce_and_ct)

    if not constant_time_equals(plaintext, DEMO_BLOB):
        print("Decrypted content does not match original.")
        sys.exit(1)

    print("Round-trip OK: encrypt → file → read → decrypt verified.")
    # In real use we would clear key/password from memory here; Python doesn't guarantee zeroing.


if __name__ == "__main__":
    _round_trip()
