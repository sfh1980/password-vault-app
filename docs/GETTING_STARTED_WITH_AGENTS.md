# Putting app completion in the hands of the agents

This guide explains how **you** trigger work and how the **main Agent** and subagents take it from there. Your role: choose the next feature or task and say "go"; the agents run the trios, handoffs, and reviews per the orchestration rules.

---

## How it works in practice

1. **You** open Cursor, start a chat with the **main Agent** (Composer/Agent), and describe what you want done (e.g. "Add the Create folder feature" or "Implement recovery key").
2. The **main Agent** reads `.cursor/rules/orchestration.mdc` and `.cursor/agents/`. It will **ask you "Proceed?"** before running any domain trio — you say yes or no.
3. When you say **yes**, the main Agent runs the right subagents in order (e.g. frontend-planner → frontend-developer → frontend-tester), passes handoffs between them, and writes handoffs to `docs/handoffs/`.
4. After each **domain trio** finishes, the main Agent asks **"Do you want to git commit?"** — you answer yes or no.
5. For **cross-domain** work (e.g. recovery key), the Agent runs the relevant trios (e.g. backend, then database, then frontend), then runs **integration-reviewer** with all handoffs to produce a master decision doc. Bugs or refactors come back to you; you reply in your own words (e.g. "have frontend-developer fix the button").
6. **Verifier** runs on the critical path (e.g. before integration-reviewer or when you say "confirm this is done"). **documentation-educator** runs after features to update HOW_IT_WORKS.md and VOCAB.md.
7. The main Agent updates **`docs/agent-status.md`** after big steps so you can see where things are.

You do **not** need to invoke each subagent by name every time. You describe the goal; the main Agent decides which trios to run and asks for your permission before starting.

---

## How to begin (first task)

### Option A: Single-domain feature (good first step)

Pick one feature that touches mostly one area, for example:

- **Create folder (UI + API)** — New "Create folder" in the web UI and a backend route. Mostly **frontend** + **backend** (no DB schema change if folders already exist).

Say something like:

> Add the Create folder feature: a way to create a new folder from the web UI, with the API and UI following our existing patterns. Use the frontend trio first, then the backend trio. Follow the orchestration rules: ask me "Proceed?" before each trio, and ask about git commit after each trio.

The main Agent should:

1. Propose running the **frontend trio** for the Create folder UI and ask **"Proceed?"**
2. After you say yes, run frontend-planner → frontend-developer → frontend-tester, write a handoff to `docs/handoffs/frontend-YYYYMMDD.md`, then ask **"Do you want to git commit?"**
3. Propose running the **backend trio** for the Create folder API and ask **"Proceed?"**
4. After you say yes, run backend-planner → backend-developer → backend-tester, write a handoff to `docs/handoffs/backend-YYYYMMDD.md`, then ask about git commit again.
5. Update `docs/agent-status.md` and optionally run **verifier** and **documentation-educator**.

### Option B: Cross-domain feature (recovery key, etc.)

For something that touches backend, database, and UI (e.g. **recovery key**):

> Implement the recovery key feature: backend and database support plus minimal UI for setting/viewing recovery key. Use the backend trio, then the database trio, then the frontend trio. After all three trios, run integration-reviewer and produce the master decision doc. Follow the orchestration rules: ask "Proceed?" before each trio, git commit prompt after each trio.

The main Agent will run the three trios in order (with your approval each time), then run **integration-reviewer** on all handoffs and produce `docs/handoffs/master-YYYYMMDD.md`. If the reviewer finds bugs, it will report them and you can reassign in your own words.

### Option C: Security or verification only

To run a single subagent without a full trio:

- **Security review:**  
  > Before we merge this, run security-auditor on the changed files. Ask me "Proceed?" first.

- **Verify current behavior:**  
  > Run the verifier to confirm unlock → add entry → lock works end-to-end.

---

## What you need to do

| Your action | When |
|-------------|------|
| **Describe the next feature or task** | At the start of a chat (e.g. "Add Create folder" or "Implement recovery key"). |
| **Say "Proceed?" / "yes" or "no"** | When the main Agent asks before running a trio or security-auditor. |
| **Say "yes" or "no" to git commit** | When the main Agent asks after each domain trio. |
| **Reassign when there are bugs** | When integration-reviewer (or a tester) reports issues; reply in your own words (e.g. "have backend-developer fix the validation"). |
| **Answer refactor suggestions** | When a tester says refactor is needed; the Agent will present the suggestion and wait for your yes/no or direction. |

---

## Suggested order of work (to complete the app)

From your project context, a sensible order is:

1. **Create folder** — API + UI (frontend trio + backend trio). Good first agent-driven task.
2. **Edit / delete entry** — API + UI (backend + frontend trios).
3. **Recovery key** — Backend + database + minimal UI (all three trios + integration-reviewer).
4. **Search** — API + UI (backend + frontend trios).
5. **Phase 5 (Docker, backup)** — When you’re ready; can be broken into smaller agent tasks (e.g. Docker first, then backup job).

Start with **Create folder** (Option A) so the agents run through the full flow (plan → code → test, handoffs, git prompt) on one clear feature. After that, you can hand off recovery key, edit/delete, search, and Docker/backup the same way.

---

## If the main Agent doesn’t follow the rules

If it runs a trio without asking "Proceed?" or skips the git prompt:

- Remind it: **"Follow the orchestration rule: ask me 'Proceed?' before running any trio, and ask about git commit after each domain trio."**
- You can point at the rule: **"See .cursor/rules/orchestration.mdc"**.

The agents are defined in `.cursor/agents/`; the main Agent can invoke them by name (e.g. `/frontend-planner`) or by describing the task and letting the Agent choose the trios.
