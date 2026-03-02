-- Multi-user: per-user auth and recovery. Users table gets username, salt, password_check, recovery columns.
-- Existing single user is backfilled from vault_meta with username 'admin'.

ALTER TABLE users ADD COLUMN username TEXT;
ALTER TABLE users ADD COLUMN salt BLOB;
ALTER TABLE users ADD COLUMN password_check_encrypted BLOB;
ALTER TABLE users ADD COLUMN recovery_salt BLOB;
ALTER TABLE users ADD COLUMN wrapped_master_key BLOB;
ALTER TABLE users ADD COLUMN recovery_qa_salt BLOB;
ALTER TABLE users ADD COLUMN recovery_qa_wrapped BLOB;
ALTER TABLE users ADD COLUMN recovery_question_1 TEXT;
ALTER TABLE users ADD COLUMN recovery_question_2 TEXT;
ALTER TABLE users ADD COLUMN recovery_question_3 TEXT;

-- Backfill existing single user from vault_meta (if any user exists)
UPDATE users SET
  username = 'admin',
  salt = (SELECT salt FROM vault_meta WHERE id = 1 LIMIT 1),
  password_check_encrypted = (SELECT password_check_encrypted FROM vault_meta WHERE id = 1 LIMIT 1),
  recovery_salt = (SELECT recovery_salt FROM vault_meta WHERE id = 1 LIMIT 1),
  wrapped_master_key = (SELECT wrapped_master_key FROM vault_meta WHERE id = 1 LIMIT 1),
  recovery_qa_salt = (SELECT recovery_qa_salt FROM vault_meta WHERE id = 1 LIMIT 1),
  recovery_qa_wrapped = (SELECT recovery_qa_wrapped FROM vault_meta WHERE id = 1 LIMIT 1),
  recovery_question_1 = (SELECT recovery_question_1 FROM vault_meta WHERE id = 1 LIMIT 1),
  recovery_question_2 = (SELECT recovery_question_2 FROM vault_meta WHERE id = 1 LIMIT 1),
  recovery_question_3 = (SELECT recovery_question_3 FROM vault_meta WHERE id = 1 LIMIT 1)
WHERE id = (SELECT id FROM users ORDER BY id LIMIT 1);

CREATE UNIQUE INDEX IF NOT EXISTS users_username ON users(username);

UPDATE schema_version SET version = 5;
