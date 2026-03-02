"""
API tests for the password vault. Use test client and temporary DB (see conftest).
No production DB or secrets in assertions; check status codes and response shape.
"""

from __future__ import annotations

import pytest

from conftest import TEST_MASTER_PASSWORD


# --- Unlock ---


def test_unlock_requires_password_or_recovery_key(client):
    """POST /unlock with neither password nor recovery_key returns 400."""
    r = client.post("/unlock", json={})
    assert r.status_code == 400
    assert "password" in r.json().get("detail", "").lower() or "recovery" in r.json().get("detail", "").lower()


def test_unlock_vault_not_initialized_returns_400(client, monkeypatch, tmp_path):
    """POST /unlock when DB has no salt (vault not inited) returns 400."""
    from vault import config
    test_db = tmp_path / "no_salt.db"
    test_db.touch()
    monkeypatch.setattr(config, "VAULT_DB_PATH", test_db)
    # Open DB so migrations run but do not init salt
    from vault import vault_db
    conn = vault_db.open_db(test_db)
    conn.close()
    r = client.post("/unlock", json={"password": "any"})
    assert r.status_code == 400
    assert "not initialized" in r.json().get("detail", "").lower()


def test_unlock_success_returns_session_id(initialized_vault):
    """POST /unlock with correct password returns 200 and session_id; no password in response."""
    r = initialized_vault.post("/unlock", json={"password": TEST_MASTER_PASSWORD})
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert "password" not in data
    assert isinstance(data["session_id"], str)
    assert len(data["session_id"]) > 0


def test_unlock_with_both_password_and_recovery_returns_400(initialized_vault):
    """POST /unlock with both password and recovery_key returns 400."""
    r = initialized_vault.post(
        "/unlock",
        json={"password": "x", "recovery_key": "y"},
    )
    assert r.status_code == 400
    assert "both" in r.json().get("detail", "").lower() or "either" in r.json().get("detail", "").lower()


def test_unlock_with_recovery_key_success(initialized_vault, session_headers, client):
    """Set up recovery, lock, then unlock with recovery_key; get 200 and session_id."""
    r_setup = client.post("/recovery/setup", headers=session_headers)
    assert r_setup.status_code == 200
    recovery_key = r_setup.json()["recovery_key"]
    assert isinstance(recovery_key, str) and len(recovery_key) > 0
    client.post("/lock", headers=session_headers)
    r_unlock = client.post("/unlock", json={"recovery_key": recovery_key})
    assert r_unlock.status_code == 200
    data = r_unlock.json()
    assert "session_id" in data
    assert isinstance(data["session_id"], str)


def test_unlock_with_recovery_key_invalid_returns_400(initialized_vault, client):
    """POST /unlock with wrong recovery key returns 400 (or recovery not set)."""
    r = client.post("/unlock", json={"recovery_key": "wrong-key-never-set"})
    assert r.status_code == 400
    assert "recovery" in r.json().get("detail", "").lower() or "invalid" in r.json().get("detail", "").lower()


# --- Lock ---


def test_lock_returns_204_with_session(initialized_vault, session_headers, client):
    """POST /lock with valid session returns 204 No Content."""
    r = client.post("/lock", headers=session_headers)
    assert r.status_code == 204
    assert r.content in (b"", None) or len(r.content) == 0


def test_lock_without_session_returns_204(client):
    """POST /lock without session is idempotent (204)."""
    r = client.post("/lock")
    assert r.status_code == 204


# --- Recovery ---


def test_recovery_setup_requires_session(initialized_vault, client):
    """POST /recovery/setup without X-Vault-Session returns 401."""
    r = client.post("/recovery/setup")
    assert r.status_code == 401


def test_recovery_setup_returns_key_and_status_becomes_configured(initialized_vault, session_headers, client):
    """POST /recovery/setup with session returns 200 and recovery_key; GET /recovery/status then returns configured true."""
    r_setup = client.post("/recovery/setup", headers=session_headers)
    assert r_setup.status_code == 200
    data = r_setup.json()
    assert "recovery_key" in data
    assert isinstance(data["recovery_key"], str)
    assert len(data["recovery_key"]) > 0

    r_status = client.get("/recovery/status", headers=session_headers)
    assert r_status.status_code == 200
    assert r_status.json().get("configured") is True


def test_recovery_status_requires_session(initialized_vault, client):
    """GET /recovery/status without X-Vault-Session returns 401."""
    r = client.get("/recovery/status")
    assert r.status_code == 401


# --- Folders ---


def test_get_folders_requires_session(initialized_vault, client):
    """GET /folders without X-Vault-Session returns 401."""
    r = client.get("/folders")
    assert r.status_code == 401


def test_get_folders_empty_returns_list(initialized_vault, session_headers, client):
    """GET /folders with session returns 200 and a list (may be empty)."""
    r = client.get("/folders", headers=session_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_post_folders_requires_session(initialized_vault, client):
    """POST /folders without session returns 401."""
    r = client.post("/folders", json={"name": "Work"})
    assert r.status_code == 401


def test_post_folders_requires_name(initialized_vault, session_headers, client):
    """POST /folders with empty name returns 422."""
    r = client.post("/folders", json={"name": ""}, headers=session_headers)
    assert r.status_code == 422


def test_post_folders_creates_and_list_includes_it(initialized_vault, session_headers, client):
    """POST /folders with valid name returns 200 and id; GET /folders then includes the new folder."""
    r = client.post("/folders", json={"name": "Test Folder"}, headers=session_headers)
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert isinstance(data["id"], int)
    folder_id = data["id"]

    r2 = client.get("/folders", headers=session_headers)
    assert r2.status_code == 200
    folders = r2.json()
    names = [f["name"] for f in folders]
    assert "Test Folder" in names


# --- Entries ---


def test_get_entries_requires_session(initialized_vault, client):
    """GET /entries without session returns 401."""
    r = client.get("/entries", params={"folder_id": 1})
    assert r.status_code == 401


def test_get_entries_requires_folder_id(initialized_vault, session_headers, client):
    """GET /entries without folder_id returns 422."""
    r = client.get("/entries", headers=session_headers)
    assert r.status_code == 422


def test_post_entries_requires_session(initialized_vault, client):
    """POST /entries without session returns 401."""
    r = client.post(
        "/entries",
        json={"folder_id": 1, "title": "Site", "username": "u", "password": "p"},
    )
    assert r.status_code == 401


def test_post_entries_requires_title(initialized_vault, session_headers, client):
    """POST /entries with empty title returns 422."""
    r = client.post(
        "/entries",
        json={"folder_id": 1, "title": "", "username": "", "password": ""},
        headers=session_headers,
    )
    assert r.status_code == 422


def test_create_folder_and_entry_flow(initialized_vault, session_headers):
    """Create a folder, then create an entry in it; GET /entries returns it. No secrets in response body."""
    r = initialized_vault.post("/folders", json={"name": "Entries Test"}, headers=session_headers)
    assert r.status_code == 200
    folder_id = r.json()["id"]

    r = initialized_vault.post(
        "/entries",
        json={
            "folder_id": folder_id,
            "title": "My Login",
            "username": "user@example.com",
            "password": "secret123",
            "url": "https://example.com",
            "notes": "Note",
        },
        headers=session_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert "password" not in data

    r = initialized_vault.get("/entries", params={"folder_id": folder_id}, headers=session_headers)
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) == 1
    assert entries[0]["title"] == "My Login"
    assert entries[0]["username"] == "user@example.com"
    # Password may be in response for display; audit log must not contain it (we don't check log here)
    assert "session_id" not in str(entries[0])


# --- Generate password ---


def test_generate_password_requires_session(initialized_vault, client):
    """GET /generate-password without session returns 401."""
    r = client.get("/generate-password")
    assert r.status_code == 401


def test_generate_password_returns_password(initialized_vault, session_headers, client):
    """GET /generate-password with session returns 200 and a password string."""
    r = client.get("/generate-password", params={"length": 16}, headers=session_headers)
    assert r.status_code == 200
    data = r.json()
    assert "password" in data
    assert isinstance(data["password"], str)
    assert len(data["password"]) == 16


def test_generate_password_respects_length(initialized_vault, session_headers, client):
    """GET /generate-password length param produces that length."""
    r = client.get("/generate-password", params={"length": 24}, headers=session_headers)
    assert r.status_code == 200
    assert len(r.json()["password"]) == 24


# --- Update entry (PATCH) ---


def test_patch_entry_requires_session(initialized_vault):
    """PATCH /entries/{id} without session returns 401."""
    r = initialized_vault.patch("/entries/1", json={"title": "Updated"})
    assert r.status_code == 401


def test_patch_entry_not_found_returns_404(initialized_vault, session_headers):
    """PATCH /entries/99999 (nonexistent) returns 404."""
    r = initialized_vault.patch("/entries/99999", json={"title": "Updated"}, headers=session_headers)
    assert r.status_code == 404


def test_patch_entry_success_returns_204(initialized_vault, session_headers):
    """Create entry, PATCH it, then GET entries shows updated title."""
    r = initialized_vault.post("/folders", json={"name": "Patch Test"}, headers=session_headers)
    assert r.status_code == 200
    folder_id = r.json()["id"]
    r = initialized_vault.post(
        "/entries",
        json={"folder_id": folder_id, "title": "Original", "username": "u", "password": "p"},
        headers=session_headers,
    )
    assert r.status_code == 200
    entry_id = r.json()["id"]
    r = initialized_vault.patch(
        "/entries/" + str(entry_id),
        json={"title": "Updated Title", "notes": "New notes"},
        headers=session_headers,
    )
    assert r.status_code == 204
    r = initialized_vault.get("/entries", params={"folder_id": folder_id}, headers=session_headers)
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) == 1
    assert entries[0]["title"] == "Updated Title"
    assert entries[0]["notes"] == "New notes"


# --- Delete entry (DELETE) ---


def test_delete_entry_requires_session(initialized_vault):
    """DELETE /entries/{id} without session returns 401."""
    r = initialized_vault.delete("/entries/1")
    assert r.status_code == 401


def test_delete_entry_not_found_returns_404(initialized_vault, session_headers):
    """DELETE /entries/99999 (nonexistent) returns 404."""
    r = initialized_vault.delete("/entries/99999", headers=session_headers)
    assert r.status_code == 404


def test_delete_entry_success_returns_204(initialized_vault, session_headers):
    """Create entry, DELETE it, then GET entries is empty."""
    r = initialized_vault.post("/folders", json={"name": "Delete Test"}, headers=session_headers)
    assert r.status_code == 200
    folder_id = r.json()["id"]
    r = initialized_vault.post(
        "/entries",
        json={"folder_id": folder_id, "title": "To Delete", "username": "", "password": ""},
        headers=session_headers,
    )
    assert r.status_code == 200
    entry_id = r.json()["id"]
    r = initialized_vault.delete("/entries/" + str(entry_id), headers=session_headers)
    assert r.status_code == 204
    r = initialized_vault.get("/entries", params={"folder_id": folder_id}, headers=session_headers)
    assert r.status_code == 200
    assert len(r.json()) == 0


# --- Search ---


def test_search_requires_session(initialized_vault):
    """GET /search without session returns 401."""
    r = initialized_vault.get("/search", params={"q": "test"})
    assert r.status_code == 401


def test_search_empty_q_returns_empty_list(initialized_vault, session_headers):
    """GET /search?q= returns []."""
    r = initialized_vault.get("/search", params={"q": ""}, headers=session_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_search_returns_matching_entries(initialized_vault, session_headers):
    """Create folder and entry, search by title and by username; results include folder_name."""
    r = initialized_vault.post("/folders", json={"name": "Search Folder"}, headers=session_headers)
    assert r.status_code == 200
    folder_id = r.json()["id"]
    r = initialized_vault.post(
        "/entries",
        json={
            "folder_id": folder_id,
            "title": "UniqueSearchTitle",
            "username": "searchuser",
            "password": "p",
            "notes": "some notes",
            "url": "https://example.com",
        },
        headers=session_headers,
    )
    assert r.status_code == 200
    r = initialized_vault.get("/search", params={"q": "UniqueSearchTitle"}, headers=session_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["title"] == "UniqueSearchTitle"
    assert data[0]["folder_name"] == "Search Folder"
    assert "folder_id" in data[0]
    r = initialized_vault.get("/search", params={"q": "searchuser"}, headers=session_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    r = initialized_vault.get("/search", params={"q": "nomatch"}, headers=session_headers)
    assert r.status_code == 200
    assert r.json() == []
