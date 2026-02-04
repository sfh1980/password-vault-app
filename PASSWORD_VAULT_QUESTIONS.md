# Password Vault Application — Design & Requirements Questions

Answer these questions so the vault can be designed and built to match your needs. You can edit this file directly; I'll refer to it when implementing.

---

## MCP Servers That Could Help (researched outside Cursor MCP directory)

- **Bitwarden MCP Server** — Zero-knowledge, local-first credential access/generation for AI agents; useful as a reference for secure credential handling and local-first design.
- **HashiCorp Vault MCP Server** — Secrets, PKI, and Vault automation via natural language; useful for patterns around secret storage and APIs.
- **SQLite MCP Server** — Local DB interaction; useful if you store vault metadata or audit logs in SQLite.
- **Security / OWASP-oriented MCPs** (e.g., BrightSec, Gopher Security) — Input validation, auth, and OWASP checklists; useful when hardening the vault app.
- **Schema / design (e.g., GibsonAI)** — Helpful for data model and schema design.

*Note: For any MCP that touches credentials, prefer local/self-hosted LLMs over cloud models.*

---

## 1. Scope & Use Case

1. **Who will use this vault?** Only you on one machine, or you across multiple devices (e.g., laptop + desktop + phone)?
initially, only 2 people will have access from laptops and mobile phones. the laptops will have Ubuntu, Windows and iOS and the phones are android and apple
2. **Primary use case?** Personal only, or also shared/family logins (e.g., Netflix, utilities)?
it will be shared/family and will take logins for multiple apps and sites and other sensitive data
3. **Rough scale?** How many entries do you expect (tens, hundreds, thousands)?
tens to hundreds max for the time being, but lets make this easily scalable

---

## 2. Security & Cryptography

4. **Master password strategy?** Single master password to unlock the vault, or do you want passkey/WebAuthn or hardware key as an option?
single master password with maybe biometrics on mobile devices
5. **Where should the vault file live?** Local only (e.g., `~/.password-vault`), or sync to a cloud folder (Dropbox, Nextcloud, iCloud) or your TrueNAS?
the vault will live in a docker container with perhaps a backup on truenas
6. **Encryption preference?** AES-256-GCM with a key derived from the master password (e.g., Argon2)—any other requirements (e.g., FIPS, specific library)?
i want at a minimum, industry standard security like bitwarden or lastpass, maybe a little stronger
7. **Session timeout?** Should the vault lock automatically after N minutes of inactivity, and if so, after how long?
what is the industry standard? lets start there
8. **Clipboard behavior?** Should copied passwords clear from clipboard after X seconds? If yes, how many seconds?
yes, clear from clipboards after 30 seconds

---

## 3. Tech Stack & Platform

9. **Interface?** CLI only, local web UI (e.g., Flask/FastAPI + browser), desktop GUI (e.g., PyQt/Tk), or CLI + web?
i do want UI's for each device as well as web, but i want to start simple, not flashy and gaudy
10. **Python version?** Any constraint (e.g., 3.10+ or 3.12+ only)?
most current up to date stable version
11. **Dependencies?** Prefer minimal dependencies (e.g., only stdlib + `cryptography`) or okay with more (e.g., SQLAlchemy, Rich for CLI)?
i'll need to do more research on dependencies, but for the time being, just whats necesary to make the app work
12. **Database/storage?** Single encrypted JSON file, SQLite DB (encrypted at rest), or something else?
given the answers to all of the questions, what would be a strong recommendation for database? as for storage, perhaps in the same docker container as the app with a backup sent to trunas?

---

## 4. Data Model & Features

13. **Fields per entry?** Besides title/name, username, password, URL—do you want notes, tags, custom fields, or “secure notes” only?
a notes field can be created
14. **Attachments?** Do you need file attachments (e.g., SSH keys, certs) stored encrypted in the vault?
yes
15. **Folders/categories?** Flat list or folders/categories (e.g., Work, Personal, Finance)?
folder/category
16. **Search?** Search by title, URL, username, tags, or all of the above?
all of the above
17. **Password generator?** Built-in generator (length, symbols, etc.)? Any character-set constraints?
when creating the entry, have choices to select based on the account. have choices for character length and set, as well as other industry standard choices as not every app or site has the same password strength standards

---

## 5. Sync, Backup & Recovery

18. **Sync across devices?** If yes, how (manual file copy, cloud folder, or a custom sync protocol)?
unless i am not understanding the difference between sync and backup, i want sync'd/backed up to truenas
19. **Backup strategy?** Automatic encrypted backups (e.g., daily to a folder or TrueNAS)? How many backups to keep?
backup daily and only keep a rolling 30 day back up
20. **Recovery?** If you forget the master password, is “no recovery by design” acceptable, or do you want a recovery key/code stored somewhere?
i want a recovery strategy. offer suggestions on what kind

---

## 6. Access Control & Audit

21. **Audit log?** Do you want a log of access/copy events (e.g., “password for X copied at 14:32”) stored inside the vault or in a separate file?
i want logs stored in a separate file for all events
22. **Export?** Do you need export to CSV/JSON (e.g., for migration to another manager)? If yes, should export be encrypted or plain (with a warning)?
no export

---

## 7. Deployment & Environment

23. **Where will it run?** Only on your Ubuntu homelab machine, or also on other Linux/Mac/Windows machines?
it will run from docker on my ubuntu homelab machine. 
24. **Installation preference?** Run from source (e.g., `python -m vault`), `pip install` from a local path, or a single executable (e.g., PyInstaller)?
for now, i think a single executable in a docker container
25. **Secrets in env?** Should the app ever read the master password from an env var or a file (e.g., for scripting), or always interactive only?
need further guidance to answer this question

---

