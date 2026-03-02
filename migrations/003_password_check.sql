-- Store a small encrypted blob so we can verify the master password on reset (e.g. when vault has no folders yet).
ALTER TABLE vault_meta ADD COLUMN password_check_encrypted BLOB;
UPDATE schema_version SET version = 3;
