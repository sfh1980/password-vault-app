# Handoffs

This directory is for **handoff documents** produced by domain subagents (frontend, backend, database) and the integration-reviewer.

- **Domain handoffs:** e.g. `frontend-YYYYMMDD.md`, `backend-YYYYMMDD.md`, `database-YYYYMMDD.md` — produced by planner → developer → tester flows.
- **Master decision:** e.g. `master-YYYYMMDD.md` — produced by integration-reviewer after reading one or more domain handoffs.

See **AGENTS_AND_RULES_DESIGN.md** in the repo root for the handoff format and when to use each agent.

You can commit handoffs to version control to keep a history of decisions, or add `docs/handoffs/*.md` to `.gitignore` to keep them local.
