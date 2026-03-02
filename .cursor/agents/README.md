# Password Vault — Agent Roster

This directory defines **custom subagents** for the project. The main Cursor Agent (or you) can invoke them explicitly (e.g. `/frontend-planner`, `/security-auditor`) or the Agent may delegate based on their `description` field.

## Domain trios (plan → code → test)

Each domain has three agents. Recommended order for a feature in that domain:

1. **Planner** — Produces a handoff (scope, decisions, API/schema contract).
2. **Developer** — Implements using the handoff; produces a short handoff for the tester.
3. **Tester** — Verifies behavior; produces pass/fail and issues.

| Domain    | Planner              | Developer               | Tester                |
|----------|----------------------|-------------------------|------------------------|
| Frontend | frontend-planner     | frontend-developer      | frontend-tester        |
| Backend  | backend-planner      | backend-developer       | backend-tester         |
| Database | database-planner     | database-developer      | database-tester        |

## Cross-domain and cross-cutting

| Agent                  | Role | When to use |
|------------------------|------|-------------|
| integration-reviewer  | Coordinate | After one or more domain trios have produced handoffs; produces a single "master decision" doc. |
| security-auditor       | Review     | When touching auth, crypto, API, or sensitive data; or on request. |
| verifier               | Verify     | After work is claimed complete; independently checks and runs tests. |
| documentation-educator | Docs    | When features or behavior change; updates HOW_IT_WORKS and EDUCATIONAL_CODE_WALKTHROUGH. |

## Handoffs

Handoffs are markdown documents that pass context between agents. Suggested location: `docs/handoffs/` (e.g. `frontend-YYYYMMDD.md`, `master-YYYYMMDD.md`). See **AGENTS_AND_RULES_DESIGN.md** in the repo root for the full workflow and handoff format.

## Invocation examples

- "Use the frontend trio to add a Create Folder button: run frontend-planner, then frontend-developer with its output, then frontend-tester."
- "/security-auditor review src/vault/crypto.py and the unlock route."
- "/verifier confirm that unlock → add entry → lock works end-to-end."
- "Run integration-reviewer on docs/handoffs/frontend-20250203.md and backend-20250203.md and produce master-20250203.md."
