-- Recovery key: store salt for recovery key derivation and master key wrapped with recovery-derived key.
-- User can unlock with recovery key if they forget the master password.
-- recovery_salt and wrapped_master_key are NULL until user runs "Set up recovery".

ALTER TABLE vault_meta ADD COLUMN recovery_salt BLOB;
ALTER TABLE vault_meta ADD COLUMN wrapped_master_key BLOB;

UPDATE schema_version SET version = 2;
