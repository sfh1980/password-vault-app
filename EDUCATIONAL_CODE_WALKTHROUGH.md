# Educational Code Walkthrough: Password Vault Application

This document explains **every important part** of the application’s code in plain language: what each line or block does, what each word or symbol means, where that code is used elsewhere in the app, and what programming standards or algorithms we use and why. It is written so that someone without a heavy programming background can follow along. **Update this document whenever we add or change code.**

---

## Table of contents

1. [Vocabulary (glossary)](#1-vocabulary-glossary)
2. [crypto.py — encryption and key derivation](#2-cryptopy--encryption-and-key-derivation)
3. [config.py — configuration from the environment](#3-configpy--configuration-from-the-environment)
4. [audit.py — audit logging](#4-auditpy--audit-logging)
5. [generator.py — password generator](#5-generatorpy--password-generator)
6. [vault_db.py — database and migrations](#6-vault_dbpy--database-and-migrations)
7. [migrations/001_initial.sql — database schema](#7-migrations001_initialsql--database-schema)
8. [api/session.py — in-memory session store](#8-apisessionpy--in-memory-session-store)
9. [api/main.py — web API and serving the UI](#9-apimainpy--web-api-and-serving-the-ui)
10. [cli.py — Phase 1 round-trip demo](#10-clipy--phase-1-round-trip-demo)
11. [web/index.html — vault web page structure](#11-webindexhtml--vault-web-page-structure)
12. [web/app.js — vault web page behavior](#12-webappjs--vault-web-page-behavior)
13. [How the pieces connect (cross-reference)](#13-how-the-pieces-connect-cross-reference)

---

## 1. Vocabulary (glossary)

These terms are used throughout the walkthrough. Definitions are in everyday language.

| Term | Plain-language meaning |
|------|-------------------------|
| **API** | A set of rules and URLs that programs use to talk to the server. For example: “send a POST request to /unlock with a password” is one API action. |
| **Argon2id** | A modern algorithm that turns a password (plus a random “salt”) into a secret key. It is deliberately slow and memory-heavy so that guessing passwords is very expensive. Recommended by security standards (e.g. OWASP, NIST). |
| **AES-256-GCM** | A way to encrypt data so that only someone with the right key can read it, and any change to the encrypted data is detected (authenticated encryption). “256” means the key is 256 bits long; “GCM” is the mode that provides both secrecy and integrity. |
| **BLOB** | “Binary large object.” A chunk of raw bytes stored in the database (e.g. encrypted data). We store encrypted text as BLOBs, not as readable text. |
| **Ciphertext** | Data that has been encrypted. You cannot read it without the key. |
| **Constant-time comparison** | Comparing two values (e.g. password vs stored value) in a way that always takes the same amount of time, so an attacker cannot learn “how close” their guess was by measuring how long the check took. |
| **Encryption** | Scrambling data so that only someone with the correct key can unscramble it. |
| **Environment variable** | A setting that lives outside the program (e.g. in the terminal or the system). The program reads it at run time (e.g. `VAULT_DB_PATH`). This keeps configuration out of the code and lets the same code run in different environments (dev vs prod). |
| **Key derivation** | Turning a password (and optionally a salt) into a fixed-length secret key that we use for encryption. We use Argon2id for this. |
| **Migration** | A script that changes the database structure (add tables, add columns) in a controlled order. We number them (001, 002, …) and run only the ones that haven’t run yet. |
| **Nonce** | “Number used once.” A random value we use once per encryption. With AES-GCM, reusing the same nonce with the same key would be a serious security mistake, so we generate a new one for every encrypt. |
| **Plaintext** | Data in readable form before encryption (or after decryption). |
| **Salt** | Random data we mix with the password when deriving a key. It makes the same password produce a different key each time (unless we reuse the same salt on purpose, which we do for one vault so we can unlock again). We store the salt with the vault so we can derive the same key when the user enters the password again. |
| **Separation of concerns** | Designing the program so that each file or module has one clear job. For example: only `crypto.py` does encryption; only `vault_db.py` talks to the database. That makes the code easier to understand, test, and change. |
| **Session** | The “logged-in” state. The server keeps a secret key in memory and gives the browser a random session id. The browser sends that id with each request so the server knows who is making the request without sending the password again. |
| **SQLite** | A database that lives in a single file (e.g. `vault.db`). No separate database server is needed. Good for small to medium apps and for backups (you copy one file). |
| **Type hint** | In Python, an annotation that says what type a variable or return value is (e.g. `str`, `int`, `bytes`). It doesn’t change how the program runs but helps humans and tools understand and catch mistakes. |
| **UTF-8** | A standard way to represent text (including letters from many languages) as bytes. We use it when converting between text and bytes for encryption or storage. |

---

## 2. crypto.py — encryption and key derivation

**File:** `src/vault/crypto.py`  
**Job:** This is the **only** place in the application that does key derivation (password → key) and encryption/decryption. No other file should implement crypto; they all call this module. That’s **separation of concerns** and reduces the risk of security mistakes.

---

### Block: Module docstring and imports

```python
"""
Key derivation and symmetric encryption for the vault.
...
"""
from __future__ import annotations

import hmac
import os
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

if TYPE_CHECKING:
    pass
```

**What each part means:**

- **`""" ... """`** — A **docstring**: a multi-line string that describes the module. It doesn’t run; it documents. Tools and humans read it to understand the file’s purpose.
- **`from __future__ import annotations`** — Makes type hints (like `bytes` and `str` in function signatures) be treated as strings that are evaluated later. This lets us use forward references and keeps compatibility with older Python style.
- **`import hmac`** — Brings in Python’s built-in `hmac` module. We use it for **constant-time comparison** of secrets (`hmac.compare_digest`).
- **`import os`** — Brings in the `os` module. We use `os.urandom()` to generate **cryptographically strong random bytes** (for nonces and salt).
- **`from typing import TYPE_CHECKING`** — `TYPE_CHECKING` is a flag that is `True` only when a type checker (e.g. mypy) is running, not at normal run time. We use it so we can write `if TYPE_CHECKING: pass` and later add imports that are only needed for type hints.
- **`from cryptography.hazmat...`** — We import **AESGCM** (encryption) and **Argon2id** (key derivation) from the `cryptography` library. “hazmat” means “hazardous materials”: low-level building blocks that must be used correctly. We use them in a limited, safe way (one nonce per encrypt, constant-time compare).
- **`if TYPE_CHECKING: pass`** — A placeholder. We could put type-only imports here so they are not loaded at run time. Right now it does nothing; it’s there for consistency and future use.

**Where this is used:** Every other module that does crypto goes through `crypto.py`. So: `vault_db.py` calls `encrypt`, `decrypt`, `random_bytes`; `cli.py` and `api/main.py` call `derive_key` (and the API gets the key via session after unlock).

**Practice:** **Explicit imports** — we only import what we need. **Docstrings** (PEP 257) — the module docstring explains the file’s role and security properties.

---

### Block: Constants (Argon2 and AES-GCM parameters)

```python
# Argon2id parameters. ...
ARGON2_ITERATIONS = 3
ARGON2_MEMORY_COST_KB = 65536  # 64 MiB
ARGON2_LANES = 8
ARGON2_KEY_LEN = 32  # AES-256
ARGON2_SALT_LEN = 16
AESGCM_NONCE_LEN = 12  # 96 bits recommended for GCM; never reuse with same key.
```

**What each part means:**

- **`ARGON2_ITERATIONS = 3`** — Number of passes the Argon2id algorithm does. Higher = slower and harder to brute-force, but more delay for the user. We use 3 as a balance.
- **`ARGON2_MEMORY_COST_KB = 65536`** — Memory size in kilobytes (65536 KB = 64 MB). Argon2id is **memory-hard**: it uses a lot of memory on purpose so that attackers need the same, making brute force expensive.
- **`ARGON2_LANES = 8`** — Parallelism (how many “lanes” run). The algorithm’s rules require `memory_cost >= 8 * lanes`; we satisfy that.
- **`ARGON2_KEY_LEN = 32`** — We want a 32-byte (256-bit) key because **AES-256** expects a 256-bit key.
- **`ARGON2_SALT_LEN = 16`** — We use a 16-byte (128-bit) random salt when deriving a key. The salt is stored with the vault so the same password always produces the same key for that vault.
- **`AESGCM_NONCE_LEN = 12`** — For AES-GCM, a 12-byte (96-bit) nonce is standard. We generate a new nonce for **every** encryption and never reuse it with the same key.

**Algorithm choice:** **Argon2id** is recommended by OWASP and NIST for password-based key derivation because it is memory-hard and resists both CPU and GPU brute force. **AES-256-GCM** gives both confidentiality and authenticity (tampering is detected).

**Where used:** `derive_key` uses the Argon2 constants; `encrypt`/`decrypt` use `AESGCM_NONCE_LEN`. `vault_db` and `cli` use `ARGON2_SALT_LEN` when generating or reading salt.

---

### Block: `derive_key(password, salt)`

```python
def derive_key(password: bytes, salt: bytes) -> bytes:
    """
    Derive a 32-byte key from the master password and salt using Argon2id.
    ...
    """
    kdf = Argon2id(
        salt=salt,
        length=ARGON2_KEY_LEN,
        iterations=ARGON2_ITERATIONS,
        lanes=ARGON2_LANES,
        memory_cost=ARGON2_MEMORY_COST_KB,
    )
    return kdf.derive(password)
```

**What each part means:**

- **`def derive_key(...)`** — Defines a function named `derive_key`.
- **`password: bytes`** — The first argument must be **bytes** (raw bytes of the password). We pass the result of `password.encode("utf-8")` from the caller so that Unicode text is converted to bytes in a standard way.
- **`salt: bytes`** — The second argument is the **salt** (e.g. 16 random bytes). Same password + same salt → same key every time.
- **`-> bytes`** — The function **returns** a value of type `bytes` (the 32-byte key).
- **`kdf = Argon2id(...)`** — **KDF** = Key Derivation Function. We create an Argon2id object with our chosen parameters and the salt.
- **`return kdf.derive(password)`** — We call `.derive()` with the password; it returns the derived key (32 bytes). That key is what we use for AES-GCM encrypt/decrypt.

**Where used:**  
- **api/main.py:** After the user sends the password, we call `derive_key(password_bytes, salt)` to get the key, then store that key in the session.  
- **cli.py:** Same idea for the round-trip demo.  
- **scripts/phase2_demo.py:** When creating the vault, we call `derive_key(password, salt)` to get the key used when creating folders and entries.

**Practice:** **Type hints** on parameters and return type. **Docstring** explains inputs, output, and the role of the salt.

---

### Block: `encrypt(key, plaintext)` and `decrypt(key, nonce_and_ciphertext)`

```python
def encrypt(key: bytes, plaintext: bytes) -> bytes:
    aes = AESGCM(key)
    nonce = os.urandom(AESGCM_NONCE_LEN)
    ciphertext = aes.encrypt(nonce, plaintext, None)
    return nonce + ciphertext

def decrypt(key: bytes, nonce_and_ciphertext: bytes) -> bytes:
    aes = AESGCM(key)
    nonce = nonce_and_ciphertext[:AESGCM_NONCE_LEN]
    ct = nonce_and_ciphertext[AESGCM_NONCE_LEN:]
    return aes.decrypt(nonce, ct, None)
```

**What each part means:**

- **`AESGCM(key)`** — Creates an AES-GCM cipher object that will use this 32-byte key for both encrypt and decrypt.
- **`os.urandom(AESGCM_NONCE_LEN)`** — Asks the operating system for 12 **cryptographically random** bytes. That is our **nonce**. We never reuse a nonce with the same key.
- **`aes.encrypt(nonce, plaintext, None)`** — Encrypts `plaintext` with this nonce. The third argument (`None`) is “associated data”; we don’t use it. The method returns the **ciphertext** (which includes the authentication tag in GCM).
- **`return nonce + ciphertext`** — We **prepend** the nonce to the ciphertext so the caller can store one blob. When decrypting, we must split it back: first 12 bytes = nonce, rest = ciphertext.
- **`nonce_and_ciphertext[:AESGCM_NONCE_LEN]`** — **Slicing**: take the first 12 bytes (the nonce). `[:12]` means “from start up to index 12.”
- **`nonce_and_ciphertext[AESGCM_NONCE_LEN:]`** — Take everything **after** the first 12 bytes (the ciphertext + tag).
- **`aes.decrypt(nonce, ct, None)`** — Decrypts and verifies the tag. If someone changed the ciphertext or used the wrong key, this raises **InvalidTag** (authenticated encryption: we detect tampering).

**Where used:**  
- **vault_db.py:** `_encrypt_field` and `_decrypt_field` call `encrypt` and `decrypt` for every sensitive column (folder name, entry title, username, password, notes, URL).  
- **cli.py:** Encrypts and decrypts the demo blob to prove the round-trip works.

**Practice:** **Single responsibility** — this module owns the “encrypt one blob / decrypt one blob” contract. **Never reuse nonce** — each call to `encrypt` gets a new nonce from `os.urandom`.

---

### Block: `constant_time_equals(a, b)` and `random_bytes(length)`

```python
def constant_time_equals(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)

def random_bytes(length: int) -> bytes:
    return os.urandom(length)
```

**What each part means:**

- **`hmac.compare_digest(a, b)`** — Compares two byte strings in **constant time**: it doesn’t stop at the first different byte. That avoids **timing side channels** where an attacker could learn how many bytes matched by measuring how long the comparison took.
- **`os.urandom(length)`** — Returns `length` bytes of **cryptographically strong** random data from the OS. We use it for salt and nonces.

**Where used:**  
- **cli.py:** Uses `constant_time_equals` to compare the salt and the decrypted blob with the originals (so we don’t leak info if they differ).  
- **vault_db.py:** Uses `random_bytes` (via `crypto.random_bytes`) when generating a new vault salt in `init_salt`.

**Practice:** **Security**: any comparison of secrets (passwords, tokens, keys) should use constant-time comparison. The standard-library way in Python is `hmac.compare_digest`.

---

## 3. config.py — configuration from the environment

**File:** `src/vault/config.py`  
**Job:** Read settings from **environment variables** so that paths and timeouts are not hard-coded. The same code can run in development or production with different values. This follows the **12-factor** idea: config in the environment.

---

### Block: Imports and `VAULT_DB_PATH`

```python
from __future__ import annotations

import os
from pathlib import Path

# DB path; default next to cwd so local dev works without setting env.
VAULT_DB_PATH: Path = Path(
    os.environ.get("VAULT_DB_PATH", "vault.db")
).resolve()
```

**What each part means:**

- **`os.environ`** — A dictionary-like object of **environment variables** (key-value pairs set in the shell or the system, e.g. `VAULT_DB_PATH=demo_vault.db`).
- **`os.environ.get("VAULT_DB_PATH", "vault.db")`** — Get the value of `VAULT_DB_PATH` if it exists; otherwise use the string `"vault.db"`. So we have a **default** and the user can override it without changing code.
- **`Path(...)`** — Turns the string into a **Path** object (from `pathlib`). Paths are easier to join and normalize than raw strings.
- **`.resolve()`** — Converts the path to an **absolute** path and resolves any `..` or `.` so we always have a full, clear path to the file.
- **`VAULT_DB_PATH: Path`** — A **type hint** saying this variable holds a `Path`. It’s the path to the SQLite database file.

**Where used:** **api/main.py** passes `config.VAULT_DB_PATH` to `vault_db.open_db()` so every API request that needs the database uses the same path. **audit.py** (indirectly) uses the audit log path from config.

**Practice:** **No secrets in code** — we don’t put database paths or timeouts in source code; we read them from the environment so they can differ per deployment.

---

### Block: `VAULT_SESSION_TIMEOUT_MINUTES` and `VAULT_AUDIT_LOG_PATH`

```python
VAULT_SESSION_TIMEOUT_MINUTES: int = int(
    os.environ.get("VAULT_SESSION_TIMEOUT_MINUTES", "15")
)

VAULT_AUDIT_LOG_PATH: Path = Path(
    os.environ.get("VAULT_AUDIT_LOG_PATH", "audit.log")
).resolve()
```

**What each part means:**

- **`int(...)`** — We convert the string from the environment to an **integer** (number of minutes). Default `"15"` → 15 minutes of inactivity before the session is considered expired.
- **`VAULT_AUDIT_LOG_PATH`** — Path to the file where we append audit lines (e.g. “unlock”, “create_entry”). Default `audit.log` in the current working directory, then resolved to an absolute path.

**Where used:**  
- **api/main.py** calls `session_store.set_timeout_minutes(config.VAULT_SESSION_TIMEOUT_MINUTES)` at startup so the in-memory session store uses the same timeout.  
- **audit.py** uses `VAULT_AUDIT_LOG_PATH` when no path is passed to `log_event` (see `_default_log_path()`).

---

## 4. audit.py — audit logging

**File:** `src/vault/audit.py`  
**Job:** Write one line to a log file for each important action (unlock, lock, list folders, list entries, create entry). We **never** write passwords or keys—only event type, optional resource id, optional user id, and timestamp. That way we have a record of “who did what when” without leaking secrets.

---

### Block: `log_event` and `_default_log_path`

```python
def log_event(
    event_type: str,
    resource_id: str | int | None = None,
    user_id: int | None = None,
    log_path: Path | None = None,
) -> None:
    path = log_path or _default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).isoformat(timespec="seconds")
    parts = [ts, event_type, str(resource_id) if resource_id is not None else "", str(user_id) if user_id is not None else ""]
    line = "\t".join(parts) + "\n"
    with path.open("a") as f:
        f.write(line)
```

**What each part means:**

- **`event_type: str`** — A short name for the action, e.g. `"unlock"`, `"lock"`, `"list_folders"`, `"create_entry"`.
- **`resource_id: str | int | None = None`** — Optional. If the action is about a specific thing (e.g. an entry id or folder id), we pass it here. `|` means “or”: the type can be str, int, or None.
- **`user_id: int | None = None`** — Optional. The user who did the action (we have one user per vault for now).
- **`log_path: Path | None = None`** — Optional. If we don’t pass a path, we use the default from config.
- **`path = log_path or _default_log_path()`** — If the caller gave a path, use it; otherwise get the default (which reads `VAULT_AUDIT_LOG_PATH` from config).
- **`path.parent.mkdir(parents=True, exist_ok=True)`** — Create the **parent folder** of the log file if it doesn’t exist. `parents=True` creates any missing parents; `exist_ok=True` doesn’t error if the folder already exists.
- **`datetime.now(UTC).isoformat(timespec="seconds")`** — Current time in **UTC** (so logs are consistent across time zones), formatted as an ISO 8601 string (e.g. `2025-02-03T22:30:00+00:00`).
- **`parts = [...]`** — We build a list of four values: timestamp, event type, resource id (or empty string), user id (or empty string). So every line has the same number of columns.
- **`"\t".join(parts)`** — Join those four values with a **tab** character so the log is tab-separated (easy to parse later).
- **`with path.open("a") as f:`** — Open the file in **append** mode (`"a"`). “Append” means we add to the end of the file and never overwrite previous lines. `with` ensures the file is closed when we’re done.
- **`f.write(line)`** — Write one line (with a newline at the end) to the file.

**Where used:** **api/main.py** calls `audit.log_event(...)` after unlock, lock, get_folders, get_entries, and post_entry. Each call passes the right `event_type` and optionally `resource_id` and `user_id`. No route writes passwords or keys to the audit log.

**Practice:** **Single place for audit** — all events go through this function. **No secrets in logs** — we only accept event type, ids, and timestamp; callers must never pass passwords or keys.

---

## 5. generator.py — password generator

**File:** `src/vault/generator.py`  
**Job:** Produce a random password of a given length using chosen character sets (uppercase, lowercase, digits, symbols). Used by the API (and thus the web UI) so password generation is consistent and uses a **cryptographically secure** random source.

---

### Block: `generate_password`

```python
def generate_password(
    length: int = 20,
    *,
    upper: bool = True,
    lower: bool = True,
    digits: bool = True,
    symbols: bool = True,
) -> str:
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
```

**What each part means:**

- **`length: int = 20`** — Default length 20 characters.
- **`*`** — In Python, everything **after** the `*` must be passed by **keyword** (e.g. `upper=True`). So we can’t accidentally pass the wrong boolean in the wrong position.
- **`upper: bool = True`** — Include uppercase letters (A–Z) if True. Same idea for `lower` (a–z), `digits` (0–9), `symbols` (the string of punctuation we defined).
- **`pool: list[str] = []`** — A list of “character set” strings. We’ll fill it with the sets the user asked for (e.g. `string.ascii_uppercase` is `"ABC...Z"`).
- **`if not pool: pool = [...]`** — If the user turned off all four, we don’t want an empty alphabet. So we fall back to letters + digits.
- **`alphabet = "".join(pool)`** — Concatenate all the chosen character sets into one long string (e.g. `"ABC...Zabc...z012...9!@#..."`). We will pick random characters from this string.
- **`secrets.choice(alphabet)`** — **secrets** is a standard-library module for **cryptographically strong** randomness. `choice(alphabet)` picks one character from `alphabet` with equal probability for each. We use this instead of `random.choice` because `random` is not meant for security-sensitive values (e.g. passwords).
- **`"".join(... for _ in range(length))`** — We call `secrets.choice(alphabet)` `length` times and join the results into one string. That string is the generated password.

**Where used:** **api/main.py** has a route `GET /generate-password` that calls `generate_password(...)` with query parameters (length, upper, lower, digits, symbols) and returns `{"password": "..."}`. The web UI “Generate” button calls that API and puts the result in the password field.

**Practice:** **Use `secrets` for security-sensitive randomness** — passwords and session ids should come from `secrets`, not `random`. **Explicit character sets** — the caller controls what goes into the password (e.g. some sites don’t allow symbols).

---

## 6. vault_db.py — database and migrations

**File:** `src/vault/vault_db.py`  
**Job:** The **only** place that talks to the SQLite database and runs SQL. It opens the DB, runs migrations, and provides functions to get/set salt, create users/folders/entries, and read folders/entries. Sensitive values are encrypted before being stored and decrypted when read; the **key** is always passed in by the caller (API or script) and never stored. This is **separation of concerns**: no SQL or schema details in the API routes.

---

### Block: Imports and `MIGRATIONS_DIR`

```python
from vault.crypto import (
    ARGON2_SALT_LEN,
    decrypt,
    encrypt,
    random_bytes,
)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"
```

**What each part means:**

- **`__file__`** — In Python, this is the path to the current source file (e.g. `.../src/vault/vault_db.py`).
- **`Path(__file__).resolve()`** — Turn it into an absolute path and resolve any `..` or `.`.
- **`.parent`** — The folder containing the file. So: `vault_db.py`’s parent is `vault/`, parent of that is `src/`, parent of that is the **project root**. So `parent.parent.parent` is the project root directory.
- **`/ "migrations"`** — The `/` operator on Path joins a folder name. So `MIGRATIONS_DIR` is the path to the `migrations` folder in the project (where `001_initial.sql` lives).

**Where used:** `_run_migrations(conn)` uses `MIGRATIONS_DIR.glob("*.sql")` to find all `.sql` files and run them in order.

---

### Block: `_encrypt_field` and `_decrypt_field`

```python
def _encrypt_field(key: bytes, value: str) -> bytes | None:
    if not value:
        return None
    return encrypt(key, value.encode("utf-8"))

def _decrypt_field(key: bytes, blob: bytes | None) -> str:
    if blob is None:
        return ""
    return decrypt(key, blob).decode("utf-8")
```

**What each part means:**

- **Leading `_`** — In Python, a name starting with `_` is a convention for “internal” to this module. Other code *can* call it, but we’re saying “prefer the public functions like create_entry / get_entries.”
- **`value.encode("utf-8")`** — Turn the string into **bytes** using the UTF-8 encoding so we can pass it to `encrypt` (which works on bytes).
- **`decrypt(key, blob).decode("utf-8")`** — Decrypt the blob to bytes, then turn those bytes back into a **string** using UTF-8.
- **`return None` for empty string** — We store empty optional fields as **NULL** in the database instead of encrypting an empty string. So the caller can distinguish “not set” from “set to empty.”
- **`return ""` for NULL** — When reading, we turn NULL back into an empty string so the API and UI always get a string, not None, for optional fields.

**Where used:** Every `create_*` function that stores sensitive text calls `_encrypt_field`; every `get_*` that reads sensitive columns calls `_decrypt_field`. So **vault_db** is the only place that knows “this column is encrypted”; the rest of the app just passes the key and gets back plain strings.

---

### Block: `_run_migrations(conn)`

This function:

1. Ensures a table **schema_version** exists and has one row with a number (the “current version”).
2. Finds all `.sql` files in `migrations/` whose names start with digits and an underscore (e.g. `001_initial.sql`).
3. Sorts them by that number and runs every file whose number is **greater** than the current version.
4. Each SQL file ends with `UPDATE schema_version SET version = N`, so the next time we know we’ve already run up to that version.

**Why migrations:** So we can change the database structure over time (add tables, add columns) in a **repeatable** way. New installs run all migrations; existing installs only run the new ones. No manual “run this SQL on your DB” steps.

**Where used:** `open_db(path)` calls `_run_migrations(conn)` right after opening the database, so every time we connect we’re on the latest schema.

---

### Block: `open_db`, `get_salt`, `init_salt`

- **open_db(path)** — Opens the SQLite file (creating the folder if needed), sets `row_factory = sqlite3.Row` so we get rows as dict-like objects (e.g. `row["id"]`), runs migrations, returns the connection. **Caller must close** the connection when done.
- **get_salt(conn)** — Reads the single row in `vault_meta` where `id = 1` and returns the `salt` column as bytes, or `None` if the vault has never been initialized.
- **init_salt(conn)** — Generates 16 random bytes, stores them in `vault_meta` (id=1), commits, and returns that salt. Called **once** when creating a new vault (e.g. Phase 2 demo or first setup).

**Where used:** **api/main.py** calls `open_db(config.VAULT_DB_PATH)` at the start of each route that needs the DB, then `get_salt(conn)` on unlock. If salt is None, it returns 400 “Vault not initialized.” **scripts/phase2_demo.py** calls `init_salt` when creating the vault, then `derive_key(password, salt)`.

---

### Block: `create_user`, `get_or_create_first_user`, `create_folder`, `create_entry`

- **create_user(conn)** — Inserts one row into `users` with a timestamp, commits, and returns the new row’s `id`. We use this for the “first user” in a single-user vault.
- **get_or_create_first_user(conn)** — Tries to select the smallest user id. If there is one, returns it; otherwise calls `create_user` and returns that id. So the API always has a valid `user_id` (e.g. for folders).
- **create_folder(conn, key, user_id, name)** — Encrypts `name` with `_encrypt_field` (or encrypts empty bytes if name is empty), inserts into `folders` with `user_id` and that blob, returns the new folder id.
- **create_entry(conn, key, folder_id, title=..., username=..., password=..., notes=..., url=...)** — Encrypts each sensitive field with the same key, inserts one row into `entries`, returns the new entry id. The `*` in the signature forces `title`, `username`, etc. to be passed as **keyword arguments** so we don’t mix up the order.

**Where used:** **api/main.py** uses `get_or_create_first_user` after a successful unlock, then `create_folder` is not used by the API yet (folders are created by the Phase 2 demo). The API uses `create_entry` in the `POST /entries` route. **scripts/phase2_demo.py** uses `create_user`, `create_folder`, `create_entry` to build the demo data.

---

### Block: `get_folders` and `get_entries`

- **get_folders(conn, key, user_id)** — Selects all rows from `folders` where `user_id` matches, ordered by id. For each row, it builds a dict with `id`, `name` (decrypted with `_decrypt_field(key, row["name_encrypted"])`), and `created_at`. Returns a list of those dicts.
- **get_entries(conn, key, folder_id)** — Same idea for `entries`: select by `folder_id`, decrypt title, username, password, notes, url, and return a list of dicts.

**Where used:** **api/main.py** `GET /folders` and `GET /entries` call these and return the list as JSON to the browser. The web UI then renders folders and entries from that JSON.

---

## 7. migrations/001_initial.sql — database schema

**File:** `migrations/001_initial.sql`  
**Job:** Defines the **initial** structure of the database: tables and columns. It is run by the migration runner in vault_db the first time the database is created.

---

### Block: schema_version and vault_meta

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
INSERT OR IGNORE INTO schema_version (version) VALUES (0);

CREATE TABLE IF NOT EXISTS vault_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    salt BLOB
);
```

**What each part means:**

- **CREATE TABLE IF NOT EXISTS** — Create the table only if it doesn’t already exist. So we can run the script again without error.
- **schema_version** — One row storing a single integer: the “version” of the schema we’ve applied. The migration runner reads this and only runs SQL files whose number is greater than this version.
- **INSERT OR IGNORE ... VALUES (0)** — Insert a row with version 0 if no row exists. “OR IGNORE” means if the row is already there (e.g. from a previous run), do nothing.
- **vault_meta** — One row per vault (we only have one vault per database for now). **id** is always 1 (`CHECK (id = 1)`). **salt** is a BLOB: the 16-byte salt we use with the master password to derive the key. We store it here so we can derive the same key every time the user unlocks.
- **BLOB** — “Binary large object”: raw bytes. We store the salt and all encrypted fields as BLOBs so we don’t try to interpret them as text.

**Where used:** The migration runner in vault_db runs this file. After it runs, `schema_version` has version 1 (see the last line of the file), and `vault_meta` exists so we can `get_salt` / `init_salt`.

---

### Block: users, folders, entries, attachments

- **users** — One row per user. We only have an **id** (auto-increment) and **created_at** (timestamp). For Phase 2–4 we use a single user (id 1); multi-user can be added later.
- **folders** — **id**, **user_id** (which user owns this folder), **name_encrypted** (BLOB: encrypted folder name), **created_at**. So we can list folders by user and decrypt the name when we have the key.
- **entries** — **id**, **folder_id** (which folder this entry is in), **title_encrypted**, **username_encrypted**, **password_encrypted**, **notes_encrypted**, **url_encrypted** (all BLOBs), **created_at**. Sensitive data is encrypted; we can still query by folder_id and id without the key.
- **attachments** — **id**, **entry_id**, **data_encrypted** (BLOB), **created_at**. Reserved for future use (e.g. encrypted file attachments).

**Practice:** **Encrypt per field** — we store ciphertext in columns so we can query by id/folder_id/created_at without decrypting. Only when we need to show or edit a value do we decrypt (in vault_db, with the key from the session).

---

## 8. api/session.py — in-memory session store

**File:** `src/vault/api/session.py`  
**Job:** Keep a mapping from **session id** (a random string we give to the browser) to **key + user_id + last_activity**. The **key** (the decryption key from the master password) never leaves the server; the browser only sends the session id (e.g. in the `X-Vault-Session` header). On each request we check if the session has **timed out** (no activity for N minutes); if so, we delete it and the user must unlock again.

---

### Block: Module-level state and `set_timeout_minutes`

```python
_sessions: dict[str, dict[str, Any]] = {}
_timeout_seconds: float = 15 * 60  # set by API on startup from config

def set_timeout_minutes(minutes: int) -> None:
    global _timeout_seconds
    _timeout_seconds = minutes * 60.0
```

**What each part means:**

- **`_sessions`** — A **dictionary** (key-value store). Key = session id (string); value = another dict with `"key"` (the bytes key), `"last_activity"` (time in seconds from a fixed point), and `"user_id"` (integer). This lives in **memory**; if the server restarts, all sessions are gone (users must unlock again).
- **`_timeout_seconds`** — How many seconds of inactivity before we consider the session expired. Default 15 * 60 = 900 seconds = 15 minutes.
- **`global _timeout_seconds`** — So that when we assign to `_timeout_seconds` inside the function, we change the **module-level** variable, not a local one. The API calls `set_timeout_minutes(config.VAULT_SESSION_TIMEOUT_MINUTES)` at startup so the timeout comes from config.

**Where used:** **api/main.py** calls `session_store.set_timeout_minutes(...)` when the app loads, then uses `create_session`, `get_session`, and `delete_session` in the unlock, lock, and protected routes.

---

### Block: `create_session`, `get_session`, `delete_session`

- **create_session(key, user_id=1)** — Generates a new random session id with `secrets.token_urlsafe(32)` (safe to use in URLs and headers), stores `{ "key": key, "last_activity": time.monotonic(), "user_id": user_id }` in `_sessions[sid]`, returns the session id. The browser will send this id back on every request.
- **get_session(session_id)** — If the id is missing or not in `_sessions`, returns None. Otherwise checks if `now - last_activity > _timeout_seconds`; if so, deletes the session and returns None (expired). If still valid, **updates** `last_activity` to now (so each request resets the inactivity timer), then returns `(key, user_id)` so the route can use the key for DB operations.
- **delete_session(session_id)** — Removes that entry from `_sessions` (e.g. when the user clicks Lock). `.pop(sid, None)` means “remove sid if present; if not present, do nothing and don’t error.”

**Practice:** **Session in memory** — we don’t put the key in a cookie or JWT; the server holds the key and only the session id is sent over the network. **Timeout on each request** — we re-check last activity and extend it on every authenticated request.

---

## 9. api/main.py — web API and serving the UI

**File:** `src/vault/api/main.py`  
**Job:** Define the **HTTP API** (unlock, lock, folders, entries, generate-password) and **serve the web UI** (HTML and JavaScript). Routes are “thin”: they parse the request, call vault_db / session / audit / crypto / generator, and return a response. No business logic lives in the route handlers; that’s in vault_db and the other modules.

---

### Block: Imports and app creation

```python
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vault import audit, config, vault_db
from vault.api import session as session_store
from vault.crypto import derive_key
from vault.generator import generate_password

app = FastAPI(title="Password Vault API", version="0.1.0")

session_store.set_timeout_minutes(config.VAULT_SESSION_TIMEOUT_MINUTES)
```

**What each part means:**

- **FastAPI** — A library for building web APIs. It handles URLs, HTTP methods, request/response bodies, and validation.
- **Header** — Lets us read an HTTP **header** from the request (e.g. `X-Vault-Session`).
- **HTTPException** — We raise this to return an error response (e.g. 401 Unauthorized, 400 Bad Request).
- **FileResponse** — Sends a file (e.g. index.html) as the response body.
- **StaticFiles** — Serves a folder of static files (e.g. app.js) under a URL path.
- **Pydantic BaseModel, Field** — We define small “models” for request and response bodies (e.g. UnlockRequest with a `password` field). FastAPI uses these to **validate** incoming JSON and to document the API.
- **app = FastAPI(...)** — The main application object. We register **routes** (URL paths and methods) on it.
- **session_store.set_timeout_minutes(...)** — So the session module uses the same timeout as in config (e.g. 15 minutes). This runs once when the app is loaded.

**Where used:** The rest of the file registers routes on `app`. When you run `uvicorn vault.api.main:app`, uvicorn loads this module and serves `app` on the port you chose.

---

### Block: Request/response models (Pydantic)

```python
class UnlockRequest(BaseModel):
    password: str = Field(..., min_length=1)

class UnlockResponse(BaseModel):
    session_id: str
```

**What each part means:**

- **BaseModel** — From Pydantic. The class describes the **shape** of the data: which keys and what types. FastAPI uses it to check that the JSON body has a `password` that is a non-empty string.
- **Field(..., min_length=1)** — The `...` means “required.” `min_length=1` means the string must have at least one character. So we reject an empty password before we ever touch the database or crypto.

**Where used:** FastAPI automatically uses `UnlockRequest` for the body of `POST /unlock` and `UnlockResponse` for the response. Same idea for CreateEntryRequest, CreateEntryResponse, GeneratePasswordResponse. This gives us **validation** and **automatic API docs** (e.g. /docs).

**Practice:** **Thin routes** — we don’t put logic in the route; we parse (and validate) the request, call a small set of functions (vault_db, session, audit, crypto), and return. **No secrets in docs** — the response models don’t expose passwords or keys; we only return things like session_id and entry id.

---

### Block: `_require_session` helper

```python
def _require_session(x_vault_session: str | None = Header(None, alias="X-Vault-Session")) -> tuple[bytes, int]:
    if not x_vault_session:
        raise HTTPException(status_code=401, detail="Missing X-Vault-Session header")
    out = session_store.get_session(x_vault_session)
    if not out:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return out
```

**What each part means:**

- **Header(None, alias="X-Vault-Session")** — FastAPI will look for an HTTP header named **X-Vault-Session** and pass its value as `x_vault_session`. If the header is missing, the default is None.
- **tuple[bytes, int]** — The return type: a pair (key, user_id). So any route that calls `_require_session` gets the decryption key and user id if the session is valid; otherwise the function raises 401 and the client gets “Unauthorized.”

**Where used:** Every route that needs an unlocked vault (get_folders, get_entries, post_entry, get_generate_password) calls `key, user_id = _require_session(x_vault_session)` at the start. So we don’t duplicate the “check session and return 401” logic in every route.

---

### Block: Routes (unlock, lock, folders, entries, generate-password)

- **POST /unlock** — Reads `body.password`, encodes to bytes, opens DB, gets salt (or 400 if None), derives key with `derive_key`, gets or creates first user, creates session with `session_store.create_session(key, user_id)`, logs `audit.log_event("unlock", ...)`, returns `{ "session_id": "..." }`. Then closes the DB connection in a `finally` block so we always release it.
- **POST /lock** — Reads the session id from the header; if present, calls `session_store.delete_session`. Logs “lock”. Returns **204 No Content** (no body). We use `Response(status_code=204)` so we don’t send any body (avoiding the “response longer than Content-Length” issue).
- **GET /folders** — Calls `_require_session` to get key and user_id, opens DB, calls `vault_db.get_folders(conn, key, user_id)`, logs “list_folders”, returns the list as JSON, closes DB.
- **GET /entries** — Same pattern: require session, open DB, call `vault_db.get_entries(conn, key, folder_id)` (folder_id comes from the query string `?folder_id=1`), log “list_entries”, return list, close DB.
- **POST /entries** — Requires session, opens DB, calls `vault_db.create_entry(conn, key, body.folder_id, title=body.title, ...)`, logs “create_entry” with resource_id=entry_id, returns `{ "id": entry_id }`, closes DB.
- **GET /generate-password** — Requires session (we don’t need the key for this), calls `generate_password(length=..., upper=..., ...)` with query parameters, returns `{ "password": "..." }`.

**Where used:** The web UI (app.js) calls these URLs with `fetch`. So the browser never sees the key; it only sends the session id and gets back folders, entries, or a generated password.

---

### Block: Serving the web UI

```python
_WEB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web"

@app.get("/", response_class=FileResponse)
def get_index():
    return FileResponse(_WEB_DIR / "index.html")

app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")
```

**What each part means:**

- **Path(__file__).resolve().parent.parent.parent.parent** — From `main.py` we go up: api → vault → src → project root. So **web** is the folder at project root named `web`.
- **GET /** — When the browser requests the root URL (e.g. http://127.0.0.1:8001/), we respond with the **contents** of `web/index.html`. So the user sees the vault login page.
- **app.mount("/static", ...)** — Any request whose path **starts with** `/static` (e.g. `/static/app.js`) is handled by **StaticFiles**: we look for a file with that name inside `_WEB_DIR`. So `/static/app.js` serves `web/app.js`. We register this **after** the API routes so that `/unlock`, `/folders`, etc. are matched first; only paths that don’t match a route fall through to the static files.

**Where used:** When you open http://127.0.0.1:8001/ in the browser, the server sends index.html; the browser then requests /static/app.js and the server sends web/app.js. So the same server serves both the API and the UI (same origin, no CORS issues).

---

## 10. cli.py — Phase 1 round-trip demo

**File:** `src/vault/cli.py`  
**Job:** A small script to **demonstrate** that encryption and decryption work end-to-end: prompt for a password, derive a key, encrypt a fixed blob, write it to a file, read it back, decrypt, and verify that the result matches. It uses the same crypto as the rest of the app (derive_key, encrypt, decrypt, constant_time_equals, random_bytes).

---

### Block: Imports and constants

```python
import getpass
...
from vault.crypto import (
    AESGCM_NONCE_LEN,
    ARGON2_SALT_LEN,
    constant_time_equals,
    decrypt,
    derive_key,
    encrypt,
    random_bytes,
)

DEMO_BLOB = b'{"entries":[]}'
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_FILE = _PROJECT_ROOT / "demo_vault.blob"
```

**What each part means:**

- **getpass** — Standard library. `getpass.getpass("Master password: ")` prompts the user for a password **without echoing** it to the terminal (so someone looking over your shoulder can’t see it).
- **DEMO_BLOB** — A small blob of bytes we encrypt (looks like a tiny JSON snippet). It’s just for the demo; the real vault uses the database.
- **_PROJECT_ROOT** — Same pattern as in main.py: from cli.py we go up (vault → src → project root). We write the demo file in the project root so it’s easy to find and is in .gitignore.
- **DEMO_FILE** — The path to `demo_vault.blob` in the project root.

**Where used:** Only when you run `python -m vault.cli`. It doesn’t call the API or vault_db; it only uses crypto and the file system.

---

### Block: `_round_trip()` and `if __name__ == "__main__"`

- **password = getpass.getpass(...).encode("utf-8")** — Get the password as a string, then convert to bytes for `derive_key`.
- **salt = random_bytes(ARGON2_SALT_LEN); key = derive_key(password, salt)** — Same as the real app: one random salt, then derive the key. For the demo we don’t store the salt in a database; we write it at the start of the file.
- **blob_to_write = salt + ciphertext** — File format: first 16 bytes = salt, then the rest = nonce + ciphertext from `encrypt`. So when we read the file we can split it and derive the key again with the same password and salt.
- **constant_time_equals(salt, salt_back)** and **constant_time_equals(plaintext, DEMO_BLOB)** — We verify the file wasn’t corrupted or tampered. We use constant-time compare so we don’t leak information if the comparison fails.
- **if __name__ == "__main__":** — This block runs only when the file is executed as a script (`python -m vault.cli`), not when another file does `import vault.cli`. So we can import the module without running the demo.

**Practice:** **No secrets in logs** — we don’t print the password or key. **Constant-time comparison** for any check involving secret data.

---

## 11. web/index.html — vault web page structure

**File:** `web/index.html`  
**Job:** The **structure** of the single-page vault UI: two main areas (login screen and vault screen), forms and buttons and placeholders for folders and entries. The **behavior** (what happens when you click or submit) is in app.js.

---

### Block: Document and head

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vault</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; ... }
    .hidden { display: none; }
    ...
  </style>
</head>
```

**What each part means:**

- **<!DOCTYPE html>** — Tells the browser this is an HTML5 document.
- **<html lang="en">** — Root element; `lang="en"` helps accessibility and translation tools.
- **<meta charset="UTF-8">** — So the browser interprets the file as UTF-8 text (needed for special characters and non-English text).
- **<meta name="viewport" ...>** — So the page scales reasonably on small screens (mobile).
- **<style> ... </style>** — **CSS** (Cascading Style Sheets) that affects this page only. For example: `* { box-sizing: border-box; }` means “every element’s width includes padding and border.” `.hidden { display: none; }` means “elements with class `hidden` are not shown.” We use that to switch between the login screen and the vault screen by adding or removing the `hidden` class.

**Where used:** The browser loads this when you request `/`. The styles apply to the elements in the body; app.js then shows/hides sections and fills lists by adding/removing the `hidden` class and changing the contents of elements like `#folder-list` and `#entry-list`.

---

### Block: Login screen and vault screen

- **id="login-screen"** — A **div** (block of content) that contains the login form. We give it an id so JavaScript can find it with `document.getElementById("login-screen")`.
- **id="login-form"** — The form with the password input and Unlock button. When the user submits, we run JavaScript that sends the password to the API and doesn’t actually “submit” the form to a new page (we call `e.preventDefault()` in app.js).
- **id="vault-screen" class="hidden"** — The vault view is hidden by default. When login succeeds, we remove `hidden` from vault-screen and add it to login-screen so only the vault is visible.
- **id="folder-list"**, **id="entry-list"** — Empty **ul** (unordered list) elements. app.js will fill them with **li** (list item) elements for each folder and each entry.
- **id="entry-detail"** — A div where we show the selected entry’s title, username, password, URL, notes and a “Copy password” button. We set its inner HTML from app.js.
- **id="add-entry-form"**, **id="new-entry-form"** — The form for creating a new entry (title, username, password, URL, notes, Generate button, Save). Hidden until the user clicks “Add entry.”
- **<script src="/static/app.js"></script>** — Tells the browser to load and run our JavaScript from the server at the path `/static/app.js`. That script then attaches behavior to the forms and buttons we defined in the HTML.

**Where used:** app.js uses these ids to grab elements (e.g. `document.getElementById("login-form")`) and to update their content or visibility. So the HTML is the “skeleton”; the JS is the “behavior.”

---

## 12. web/app.js — vault web page behavior

**File:** `web/app.js`  
**Job:** All the **behavior** of the vault UI: store and send the session id, call the API, show/hide screens, list folders and entries, copy password and clear clipboard after 30 seconds, inactivity timer that locks after 15 minutes. Written in plain JavaScript (no framework). No passwords or keys are logged to the console.

---

### Block: Constants and element references

```javascript
(function () {
  'use strict';

  const SESSION_TIMEOUT_MINUTES = 15;
  const CLIPBOARD_CLEAR_MS = 30000;

  let inactivityTimerId = null;
  let clipboardClearTimerId = null;

  const loginScreen = document.getElementById('login-screen');
  const vaultScreen = document.getElementById('vault-screen');
  ...
```

**What each part means:**

- **(function () { ... })();** — An **IIFE** (Immediately Invoked Function Expression). We wrap all our code in a function and call it right away. That way our variables (like `loginScreen`, `inactivityTimerId`) are **local** to this function and don’t pollute the global scope. So we don’t accidentally clash with other scripts or leave temporary variables in the window.
- **'use strict';** — Enables **strict mode**: certain unsafe or ambiguous behaviors are errors. Good practice for maintainable code.
- **SESSION_TIMEOUT_MINUTES** — Matches the server’s default: after 15 minutes with no clicks or keypresses we call lock.
- **CLIPBOARD_CLEAR_MS** — 30 seconds in milliseconds. After we copy a password to the clipboard, we wait this long and then clear the clipboard.
- **inactivityTimerId** — The id returned by `setTimeout`. We need it so we can **clear** the timer when the user does something (reset the 15-minute countdown) or when we lock.
- **document.getElementById('login-screen')** — Finds the one element in the HTML that has `id="login-screen"`. We store a reference so we don’t have to look it up every time we want to show or hide the login screen.

**Where used:** Every function in the file that needs to show/hide a screen or reset the timer uses these constants and element references.

---

### Block: Session storage and `api()` helper

```javascript
function getSessionId() {
  return sessionStorage.getItem('vault_session_id');
}
function setSessionId(id) {
  if (id) sessionStorage.setItem('vault_session_id', id);
  else sessionStorage.removeItem('vault_session_id');
}

function api(url, options = {}) {
  const sid = getSessionId();
  const headers = new Headers(options.headers || {});
  if (sid) headers.set('X-Vault-Session', sid);
  ...
  return fetch(url, { ...options, headers }).then(function (res) {
    if (res.status === 401) {
      setSessionId(null);
      showLogin('Session expired or invalid.');
      throw new Error('Unauthorized');
    }
    return res;
  });
}
```

**What each part means:**

- **sessionStorage** — A small key-value store in the browser that lasts only for the **current tab**. When the user closes the tab, it’s cleared. We store the session id here so that after a page refresh we can try to use it again (and the server will tell us if it’s expired).
- **api(url, options)** — A helper that **always** adds the `X-Vault-Session` header if we have a session id, and optionally sets `Content-Type: application/json` if we’re sending a body. It uses **fetch** to send the HTTP request. In the `.then()`, we check **res.status**: if it’s **401** (Unauthorized), we clear the session id, show the login screen with a message, and **throw** so the caller’s `.catch()` runs. Otherwise we return the response so the caller can do `res.json()` or similar.
- **headers.set('X-Vault-Session', sid)** — The server expects the session id in this header so it can look up the key in its in-memory store. We never send the password again after unlock.

**Where used:** Every place we call the server (unlock, lock, folders, entries, create entry, generate password) goes through `api(...)`. So we don’t duplicate the “add session header” and “handle 401” logic.

---

### Block: showLogin, showVault, lock, inactivity timer

- **showLogin(message)** — Hides the vault screen, shows the login screen, hides error/message areas and optionally sets a message (e.g. “Locked.”). Stops the inactivity timer so we’re not running a timer when no one is logged in.
- **showVault()** — Hides the login screen, shows the vault screen, hides errors, starts the inactivity timer.
- **startInactivityTimer()** — Clears any existing timer, then sets a new one: after `SESSION_TIMEOUT_MINUTES * 60 * 1000` milliseconds, call **lock()**.
- **resetInactivityTimer()** — Called when the user clicks or types in the vault area. If we have a session, we restart the inactivity timer (so 15 minutes without any action will lock).
- **lock()** — If we have a session id, send **POST /lock** (so the server deletes the session). Clear the session id in the browser, then show the login screen with “Locked.”

**Where used:** Login form submit calls showVault and loadFolders; lock button and timeout call lock; vault area click/keydown call resetInactivityTimer. So the UI always reflects “logged in” vs “logged out” and the server and client stay in sync.

---

### Block: copyPassword, loadFolders, loadEntries, showEntryDetail, escapeHtml

- **copyPassword(plaintext)** — Calls `navigator.clipboard.writeText(plaintext)` to put the password in the clipboard. Then sets a timer for `CLIPBOARD_CLEAR_MS`; when it fires, we call `navigator.clipboard.writeText('')` to clear the clipboard. We don’t keep the password in a variable after this; we only use it for the one copy. **Practice:** No secrets kept in JS longer than needed; clipboard cleared per requirement.
- **loadFolders()** — Calls **GET /folders**, parses JSON, clears the folder list in the DOM, then for each folder creates an **li** with a **button** (the folder name). Clicking the button calls loadEntries for that folder and stores the folder id on the “Add entry” button so we know which folder to add to. Appends each li to **folder-list**.
- **loadEntries(folderId)** — Calls **GET /entries?folder_id=...**, parses JSON, clears the entry list, then for each entry creates an **li** with the title and a “Copy password” button. Clicking the row (except the copy button) shows the entry detail; clicking “Copy password” copies that entry’s password and resets the inactivity timer.
- **showEntryDetail(entry)** — Builds HTML for the entry (title, username, URL as link, notes, and a “Copy password” button). We use **escapeHtml(entry.title)** etc. so that if the title or notes contain `<` or `>`, they are turned into safe text and not interpreted as HTML (avoids **XSS** — injecting script via content). Then we remove the `hidden` class and attach a click handler to the new “Copy password” button.
- **escapeHtml(s)** — Creates a temporary **div**, sets its **textContent** to the string (so the browser doesn’t interpret tags), then reads **innerHTML** back. That gives us an escaped version of the string (e.g. `<` becomes `&lt;`). So we can safely insert user content into the page without allowing script injection.

**Where used:** loadFolders runs after login and when we first load the page with an existing session. loadEntries runs when the user clicks a folder. showEntryDetail runs when the user clicks an entry. copyPassword runs when the user clicks “Copy password” in the list or in the detail view.

---

### Block: Login form submit, lock button, add entry form, generate password, initial load

- **loginForm.addEventListener('submit', ...)** — When the user submits the login form, we **prevent the default** (no full-page submit). We get the password from the input, call **POST /unlock** with `JSON.stringify({ password: password })`, then in the success path we save the **session_id** from the response with setSessionId, clear the password field, show the vault, and load folders. On error we show loginError unless the error was “Unauthorized” (we already showed login in the 401 handler).
- **lockBtn.addEventListener('click', lock)** — Clicking Lock calls lock().
- **vaultActivity.addEventListener('click', resetInactivityTimer)** and **keydown** — So any click or keypress in the vault area resets the 15-minute timer.
- **addEntryBtn** — When clicked, we check if a folder is selected (addEntryBtn.dataset.folderId). If not, we show “Select a folder first.” Otherwise we show the add-entry form and set the hidden folder_id input so the form knows which folder to use.
- **newEntryForm.addEventListener('submit', ...)** — We build a **payload** object with folder_id, title, username, password, url, notes from the form fields, send **POST /entries** with that payload, then on success reset the form, hide it, reload entries for that folder, and reset the inactivity timer.
- **generate-password-btn** — Clicking it calls **GET /generate-password?length=20**, gets the JSON, and sets the new-password input’s value to the returned password.
- **At the bottom:** If **getSessionId()** returns something, we try **GET /folders**. If the response is ok, we show the vault and load folders. If not (e.g. 401), we show the login screen. So if the user refreshes the page and the session is still valid, they stay logged in; if the session expired, they see the login form.

**Where used:** These are the **event handlers** that connect user actions (click, submit) to API calls and UI updates. So the whole flow (login → list folders → list entries → view/copy → add entry → lock) is wired up here.

---

## 13. How the pieces connect (cross-reference)

| Code / concept | Used by | How / why |
|----------------|--------|-----------|
| **crypto.derive_key** | api/main.py (unlock), cli.py, scripts/phase2_demo.py | After the user sends the password, we need a key to encrypt/decrypt. We get the salt from the DB (or from the demo file), then derive_key(password, salt). The key is then stored in the session (API) or used once (CLI/demo). |
| **crypto.encrypt / decrypt** | vault_db.py (_encrypt_field / _decrypt_field) | vault_db encrypts every sensitive string before writing to the DB and decrypts when reading. So the DB only ever sees ciphertext; the key never touches the DB. |
| **crypto.random_bytes** | vault_db.init_salt, cli.py (salt for demo file) | We need random bytes for salt and (inside encrypt) for nonce. Only crypto and vault_db/cli generate these; no other module should. |
| **config.VAULT_DB_PATH** | api/main.py (open_db in every route) | So the API always uses the same database file that the user configured (e.g. demo_vault.db). |
| **config.VAULT_SESSION_TIMEOUT_MINUTES** | api/main.py (set_timeout_minutes at startup) | So the in-memory session store uses the same timeout as the config (e.g. 15 minutes). |
| **config.VAULT_AUDIT_LOG_PATH** | audit._default_log_path() | So we write the audit log to the file the user configured (e.g. audit.log). |
| **audit.log_event** | api/main.py (after unlock, lock, list_folders, list_entries, create_entry) | Every sensitive action is recorded with event type, optional resource_id and user_id, and timestamp. No passwords or keys are passed. |
| **generator.generate_password** | api/main.py (GET /generate-password) | The API route calls it with query parameters and returns the password in JSON. The web UI “Generate” button calls that route and fills the password field. |
| **vault_db.open_db** | api/main.py (every route that needs the DB), scripts/phase2_demo.py | Opens the SQLite file and runs migrations. Caller must close the connection when done (main.py uses try/finally). |
| **vault_db.get_salt / init_salt** | api/main.py (unlock: get_salt), phase2_demo.py (init_salt on first run) | Unlock needs the salt to derive the key; the demo creates the salt when creating a new vault. |
| **vault_db.get_or_create_first_user** | api/main.py (unlock) | So we have a user_id to pass to create_session and to get_folders. For now we have one user per vault. |
| **vault_db.get_folders / get_entries** | api/main.py (GET /folders, GET /entries) | The routes get (key, user_id) from the session, open the DB, call these, return the list as JSON. The browser then renders the lists. |
| **vault_db.create_entry** | api/main.py (POST /entries) | The route gets the key from the session and the entry fields from the request body, then calls create_entry and returns the new id. |
| **session_store.create_session** | api/main.py (unlock) | After we derive the key, we store it in memory under a new session id and return that id to the browser. |
| **session_store.get_session** | api/main.py (_require_session, then every protected route) | Each request sends the session id in the header; we look it up and get (key, user_id) or None (then 401). We also update last_activity so the timeout is extended. |
| **session_store.delete_session** | api/main.py (lock) | When the user locks, we remove the session from memory so the key is no longer available. |
| **web/index.html** | Browser requests / | main.py serves this file as the response for GET /. The browser parses it and then requests /static/app.js. |
| **web/app.js** | Browser loads it via <script src="/static/app.js"> | main.py serves it from the web/ folder. It runs in the browser and calls the API (unlock, lock, folders, entries, etc.) and updates the HTML (lists, detail, forms). |

---

*This walkthrough was written after Phases 1–4 (crypto, DB, API, web UI). When we add recovery key, create folder, edit/delete, search, or other features, add the new code to the right file section above and update this cross-reference table and HOW_IT_WORKS.md.*
