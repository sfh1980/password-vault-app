-- Recovery via 3 security questions: store questions (plaintext) and wrapped master key (derived from answers).
-- User can recover with either the long recovery key OR the 3 answers (if set).
ALTER TABLE vault_meta ADD COLUMN recovery_qa_salt BLOB;
ALTER TABLE vault_meta ADD COLUMN recovery_qa_wrapped BLOB;
ALTER TABLE vault_meta ADD COLUMN recovery_question_1 TEXT;
ALTER TABLE vault_meta ADD COLUMN recovery_question_2 TEXT;
ALTER TABLE vault_meta ADD COLUMN recovery_question_3 TEXT;
UPDATE schema_version SET version = 4;
