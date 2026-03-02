# Glossary (VOCAB)

Terms used in HOW_IT_WORKS.md and the project, in plain language. The documentation-educator agent keeps this in sync when features or behavior change.

---

- **Session** — The period after you unlock the vault. The app keeps you logged in until you lock, close the tab, or hit the inactivity timeout.
- **Session ID** — A secret token stored in your browser (sessionStorage) and sent with each request so the server knows it’s you. Never shared in the UI or logs.
- **Handoff** — A short document passed between agents (e.g. planner → developer → tester) describing scope, decisions, and what was done.
- **Trio** — The three agents for one domain: planner, developer, tester (e.g. frontend trio = frontend-planner, frontend-developer, frontend-tester).
- **Recovery key** — A one-time secret (shown once when you set it up) that can unlock the vault if you forget your master password. You must store it offline (e.g. on paper or in a safe place). The app does not store the recovery key itself; it stores an encrypted copy of the master key that can only be unlocked with the recovery key.

*(Add more terms as the app grows.)*
