"""
Key derivation and symmetric encryption for the vault.

Separation of concerns: this module is the single place for KDF and
encrypt/decrypt. Callers (API, CLI) never implement crypto themselves.

- Argon2id: memory-hard KDF so brute force is expensive (OWASP/NIST).
- AES-256-GCM: authenticated encryption; each encryption uses a fresh nonce.
- Constant-time comparison for any secret check (timing side-channel safety).
"""

from __future__ import annotations

import hmac
import os
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

if TYPE_CHECKING:
    pass

# Argon2id parameters. Memory-hard and iteration count slow down brute force.
# iterations=3: number of passes (higher = slower, more secure).
# memory_cost: size in KiB (65536 = 64 MiB). Minimum 8*lanes.
# lanes=8: parallelism; memory_cost must be >= 8*lanes.
# Salt must be unique per vault/use; we pass it in so the same salt can be stored with the blob.
ARGON2_ITERATIONS = 3
ARGON2_MEMORY_COST_KB = 65536  # 64 MiB
ARGON2_LANES = 8
ARGON2_KEY_LEN = 32  # AES-256
ARGON2_SALT_LEN = 16
AESGCM_NONCE_LEN = 12  # 96 bits recommended for GCM; never reuse with same key.


def derive_key(password: bytes, salt: bytes) -> bytes:
    """
    Derive a 32-byte key from the master password and salt using Argon2id.

    Salt must be unique per vault/file (e.g. random 16 bytes). Same password + salt
    always yields the same key, so we store salt with the ciphertext to decrypt later.
    """
    kdf = Argon2id(
        salt=salt,
        length=ARGON2_KEY_LEN,
        iterations=ARGON2_ITERATIONS,
        lanes=ARGON2_LANES,
        memory_cost=ARGON2_MEMORY_COST_KB,
    )
    return kdf.derive(password)


def encrypt(key: bytes, plaintext: bytes) -> bytes:
    """
    Encrypt plaintext with AES-256-GCM; returns nonce + ciphertext+tag.

    We generate a new nonce per call and prepend it to the ciphertext so the
    caller can store one blob. Never reuse a nonce with the same key.
    """
    aes = AESGCM(key)
    nonce = os.urandom(AESGCM_NONCE_LEN)
    ciphertext = aes.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt(key: bytes, nonce_and_ciphertext: bytes) -> bytes:
    """
    Decrypt data produced by encrypt(): nonce (12 bytes) + ciphertext+tag.

    Raises InvalidTag on tampering or wrong key (GCM gives authenticity).
    """
    aes = AESGCM(key)
    nonce = nonce_and_ciphertext[:AESGCM_NONCE_LEN]
    ct = nonce_and_ciphertext[AESGCM_NONCE_LEN:]
    return aes.decrypt(nonce, ct, None)


def constant_time_equals(a: bytes, b: bytes) -> bool:
    """
    Compare two bytestrings in constant time. Use for passwords/tokens/keys.

    Avoids timing side channels: early return on first differing byte would
    leak information. hmac.compare_digest is the standard-library solution.
    """
    return hmac.compare_digest(a, b)


def random_bytes(length: int) -> bytes:
    """Generate cryptographically strong random bytes (e.g. for salt)."""
    return os.urandom(length)
