# Agents and workflow

How to hand work to the agents, get started, and where handoffs and status live. For the full doc index see [DOCS.md](DOCS.md).

---

## Table of contents

1. [How it works in practice](#1-how-it-works-in-practice)
2. [How to begin (first task)](#2-how-to-begin-first-task)
3. [What you need to do](#3-what-you-need-to-do)
4. [Agent workflow status](#4-agent-workflow-status)
5. [Handoffs](#5-handoffs)

---

## 1. How it works in practice

1. **You** open Cursor, start a chat with the **main Agent**, and describe what you want (e.g. "Add the Create folder feature" or "Implement recovery key").
2. The **main Agent** reads `.cursor/rules/orchestration.mdc` and `.cursor/agents/`. It will **ask you "Proceed?"** before running any domain trio.
3. When you say **yes**, the main Agent runs the right subagents in order (e.g. frontend-planner → frontend-developer → frontend-tester), passes handoffs between them, and writes handoffs to `docs/handoffs/`.
4. After each **domain trio** the main Agent asks **"Do you want to git commit?"** — you answer yes or no.
5. For **cross-domain** work (e.g. recovery key), the Agent runs the relevant trios, then **integration-reviewer** with all handoffs to produce a master decision doc. Bugs come back to you; you reassign in your own words.
6. **Verifier** runs on the critical path when needed. **documentation-educator** runs after features to update the user guide and VOCAB.
7. The main Agent updates **docs/agent-status.md** after big steps.

You do **not** need to invoke each subagent by name. Describe the goal; the main Agent decides which trios to run and asks for your permission before starting.

---

## 2. How to begin (first task)

### Option A: Single-domain feature

Example: **Create folder (UI + API)**. Say something like:

> Add the Create folder feature: a way to create a new folder from the web UI, with the API and UI following our existing patterns. Use the frontend trio first, then the backend trio. Follow the orchestration rules: ask me "Proceed?" before each trio, and ask about git commit after each trio.

The main Agent should run the frontend trio (with your approval), then the backend trio, write handoffs, and ask about git commit after each.

### Option B: Cross-domain feature

Example: **Recovery key**. Say something like:

> Implement the recovery key feature: backend and database support plus minimal UI. Use the backend trio, then the database trio, then the frontend trio. After all three, run integration-reviewer and produce the master decision doc. Ask "Proceed?" before each trio and about git commit after each.

### Option C: Security or verification only

- **Security review:** "Before we merge this, run security-auditor on the changed files. Ask me 'Proceed?' first."
- **Verify behavior:** "Run the verifier to confirm unlock → add entry → lock works end-to-end."

---

## 3. What you need to do

| Your action | When |
|-------------|------|
| **Describe the next feature or task** | At the start of a chat. |
| **Say "Proceed?" / "yes" or "no"** | When the main Agent asks before running a trio or security-auditor. |
| **Say "yes" or "no" to git commit** | When the main Agent asks after each domain trio. |
| **Reassign when there are bugs** | When integration-reviewer or a tester reports issues; reply in your own words (e.g. "have backend-developer fix the validation"). |
| **Answer refactor suggestions** | When a tester says refactor is needed; the Agent presents the suggestion and waits for your direction. |

---

## 4. Agent workflow status

The main Agent updates **docs/agent-status.md** after big steps so you can see at a glance where the workflow is.

| Field | Value |
|-------|--------|
| **Last step completed** | (none yet) |
| **Next step** | (waiting for instruction) |
| **Last updated** | — |

Example after a frontend trio: "Last: frontend-tester completed 2025-02-03; next: backend-planner."

---

## 5. Handoffs

**Location:** `docs/handoffs/`

- **Domain handoffs:** e.g. `frontend-YYYYMMDD.md`, `backend-YYYYMMDD.md`, `database-YYYYMMDD.md` — produced by planner → developer → tester flows.
- **Master decision:** e.g. `master-YYYYMMDD.md` — produced by integration-reviewer after reading one or more domain handoffs.

See [Design and planning](DESIGN.md#3-agents-and-rules-design) for handoff format and when to use each agent. You can commit handoffs to version control for history, or add `docs/handoffs/*.md` to `.gitignore` to keep them local.

---

## If the main Agent doesn’t follow the rules

If it runs a trio without asking "Proceed?" or skips the git prompt:

- Remind it: **"Follow the orchestration rule: ask me 'Proceed?' before running any trio, and ask about git commit after each domain trio."**
- Point at the rule: **"See .cursor/rules/orchestration.mdc"**.

Agents are defined in `.cursor/agents/`; the main Agent can invoke them by name or by task description.
