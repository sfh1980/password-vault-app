"""
Pytest fixtures for vault tests. Sets a temporary DB and audit log so we never
touch production data. Env vars must be set before any vault import so config picks them up.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Use a temp dir for test DB and audit log (no production files touched).
_test_dir = tempfile.mkdtemp(prefix="vault_test_")
os.environ["VAULT_DB_PATH"] = os.path.join(_test_dir, "vault.db")
os.environ["VAULT_AUDIT_LOG_PATH"] = os.path.join(_test_dir, "audit.log")

from fastapi.testclient import TestClient

from vault import config, vault_db
from vault.api.main import app

# Password used in tests for unlock. Vault is inited with random salt in initialized_vault.
TEST_MASTER_PASSWORD = "test-master-password"


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client. Uses test DB from env (set above)."""
    return TestClient(app)


@pytest.fixture
def initialized_vault(client: TestClient) -> TestClient:
    """Ensure the test DB has salt and at least one user so POST /unlock can succeed."""
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        if vault_db.get_salt(conn) is None:
            vault_db.init_salt(conn)
        vault_db.get_or_create_first_user(conn)
    finally:
        conn.close()
    return client


@pytest.fixture
def session_headers(initialized_vault: TestClient) -> dict[str, str]:
    """Unlock once and return headers with X-Vault-Session for authenticated requests."""
    r = initialized_vault.post(
        "/unlock",
        json={"password": TEST_MASTER_PASSWORD},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    session_id = data["session_id"]
    return {"X-Vault-Session": session_id}
