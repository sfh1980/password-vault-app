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
# High rate limit in tests so many auth requests (setup/unlock/signup) don't trigger 429.
os.environ["VAULT_RATE_LIMIT_AUTH_PER_MINUTE"] = "1000"

from fastapi.testclient import TestClient

from vault import config, vault_db
from vault.api.main import app

# Username and password used in tests. initialized_vault creates first user with these.
TEST_USERNAME = "testuser"
TEST_MASTER_PASSWORD = "test-master-password"


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client. Uses test DB from env (set above)."""
    return TestClient(app)


@pytest.fixture
def initialized_vault(client: TestClient) -> TestClient:
    """Ensure the test DB has at least one user so POST /unlock can succeed."""
    conn = vault_db.open_db(config.VAULT_DB_PATH)
    try:
        if not vault_db.vault_initialized(conn):
            vault_db.init_first_user(conn, TEST_USERNAME, TEST_MASTER_PASSWORD)
    finally:
        conn.close()
    return client


@pytest.fixture
def session_headers(initialized_vault: TestClient) -> dict[str, str]:
    """Unlock once and return headers with X-Vault-Session for authenticated requests."""
    r = initialized_vault.post(
        "/unlock",
        json={"username": TEST_USERNAME, "password": TEST_MASTER_PASSWORD},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    session_id = data["session_id"]
    return {"X-Vault-Session": session_id}
