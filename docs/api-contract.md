# API contract (frontend ↔ backend)

Short written contract so frontend and backend agents stay aligned. Update this when adding or changing endpoints. Planner handoffs can reference this file or paste the relevant section.

---

## Current endpoints

- **POST /unlock** — Body: exactly one of `{ "password": string }` or `{ "recovery_key": string }`. Response: `{ "session_id": string }`. Sets session; use session_id in `X-Vault-Session` header for subsequent requests. 400 if neither/both or invalid recovery key.
- **POST /lock** — Header: `X-Vault-Session`. Response: 204 No Content. Discards session.
- **GET /folders** — Header: `X-Vault-Session`. Response: list of `{ "id": number, "name": string }` (name may be decrypted server-side).
- **GET /entries** — Header: `X-Vault-Session`. Query: `folder_id` (optional). Response: list of entries (ids, titles, etc.; sensitive fields decrypted).
- **POST /entries** — Header: `X-Vault-Session`. Body: `{ "folder_id": number, "title": string, "username": string, "password": string, "notes": string, "url": string }`. Response: `{ "id": number }`.
- **PATCH /entries/{entry_id}** — Header: `X-Vault-Session`. Body: optional `{ "title", "username", "password", "notes", "url" }` (only provided fields are updated). Response: 204 No Content. 404 if entry not found or not owned.
- **DELETE /entries/{entry_id}** — Header: `X-Vault-Session`. Response: 204 No Content. 404 if entry not found or not owned.
- **GET /search** — Header: `X-Vault-Session`. Query: `q` (search string). Searches title, username, notes, URL (case-insensitive). Response: list of entries with `folder_id` and `folder_name` added. Empty `q` returns `[]`.
- **POST /recovery/setup** — Header: `X-Vault-Session`. Response: `{ "recovery_key": string }` (show once; user stores offline). Stores wrapped master key so user can unlock with recovery key if they forget the password.
- **GET /recovery/status** — Header: `X-Vault-Session`. Response: `{ "configured": boolean }`.
- **GET /generate-password** — Query: `length`, `upper`, `lower`, `digits`, `symbols`. Response: `{ "password": string }`. (Session required.)

401 on missing or invalid session.

---

*(Add new endpoints and request/response shapes here as the app grows.)*
