# API contract (frontend ↔ backend)

Short written contract so frontend and backend agents stay aligned. Update this when adding or changing endpoints. Planner handoffs can reference this file or paste the relevant section.

---

## Current endpoints

- **GET /vault/status** — No auth. Response: `{ "initialized": boolean }`. Used to show first-time setup vs unlock form.
- **POST /setup** — Body: `{ "password": string }`. Response: `{ "session_id": string }`. First-time only: initializes vault (salt, password check, first user), returns session. 400 if vault already initialized.
- **POST /vault/reset** — Body: `{ "password": string }`. Verifies password, then deletes the DB file. Response: 200 `{ "message": string }`. 401 if wrong password. For testing; next visit shows setup again.
- **POST /unlock** — Body: exactly one of `{ "password": string }`, `{ "recovery_key": string }`, or `{ "recovery_answers": [ string, string, string ] }` (3 answers for security-question recovery). Response: `{ "session_id": string }`. 400 if none/multiple or invalid.
- **POST /lock** — Header: `X-Vault-Session`. Response: 204 No Content. Discards session.
- **GET /folders** — Header: `X-Vault-Session`. Response: list of `{ "id": number, "name": string }` (name may be decrypted server-side).
- **GET /entries** — Header: `X-Vault-Session`. Query: `folder_id` (optional). Response: list of entries (ids, titles, etc.; sensitive fields decrypted).
- **POST /entries** — Header: `X-Vault-Session`. Body: `{ "folder_id": number, "title": string, "username": string, "password": string, "notes": string, "url": string }`. Response: `{ "id": number }`.
- **PATCH /entries/{entry_id}** — Header: `X-Vault-Session`. Body: optional `{ "title", "username", "password", "notes", "url" }` (only provided fields are updated). Response: 204 No Content. 404 if entry not found or not owned.
- **DELETE /entries/{entry_id}** — Header: `X-Vault-Session`. Response: 204 No Content. 404 if entry not found or not owned.
- **GET /search** — Header: `X-Vault-Session`. Query: `q` (search string). Searches title, username, notes, URL (case-insensitive). Response: list of entries with `folder_id` and `folder_name` added. Empty `q` returns `[]`.
- **POST /recovery/setup** — Header: `X-Vault-Session`. Response: `{ "recovery_key": string }` (show once; user stores offline). Stores wrapped master key so user can unlock with recovery key.
- **POST /recovery/setup-questions** — Header: `X-Vault-Session`. Body: `{ "question_1", "question_2", "question_3", "answer_1", "answer_2", "answer_3" }` (all strings). Response: 204. Stores 3 questions (plaintext) and wrapped master key derived from answers; user can unlock with the 3 answers.
- **GET /recovery/status** — Header: `X-Vault-Session`. Response: `{ "configured": boolean, "key_configured": boolean, "questions_configured": boolean, "questions": [ string, string, string ] | null }`.
- **GET /recovery/questions** — No auth. Response: `{ "questions_configured": boolean, "questions": [ string, string, string ] | null }`. Used by unlock page to show the 3 question fields when questions recovery is set.
- **GET /generate-password** — Query: `length`, `upper`, `lower`, `digits`, `symbols`. Response: `{ "password": string }`. (Session required.)

401 on missing or invalid session.

---

*(Add new endpoints and request/response shapes here as the app grows.)*
