# Agents, Subagents, and .cursor Setup — Design for Password Vault

This document designs a **multi-agent setup** for this project: domain-specific subagents (frontend, backend, database), each with **plan / code / test** roles, plus **cross-domain coordination** and other `.cursor` additions. It also explains how this fits Cursor’s actual subagent model and gives **20+ questions** to refine your request.

---

## How Cursor Subagents Actually Work (Important Constraint)

- **No nested subagents.** Subagents are single-level: the **main Agent** (or you) invokes them. They cannot launch other subagents.
- **No built-in “chat between agents.”** Subagents don’t have a shared chat. “Agreement” and “communication between groups” are achieved by:
  - **Sequential runs:** Agent A runs → produces output (e.g. a handoff doc) → parent passes that to Agent B → Agent B runs → etc.
  - **Parallel runs:** Parent runs several subagents at once, then **synthesizes** their outputs (or you compare).
- **Handoffs** = structured output (e.g. markdown in the repo or in the subagent’s reply) that the next agent or the parent is instructed to read and use.

So “3 subagents in each section talking to each other, then coming to agreement and communicating with other groups of 3” is implemented as:

1. **Within a domain (e.g. Frontend):** Parent runs **planner → developer → tester** in **sequence**, each consuming the previous output (handoff). “Agreement” = the tester’s pass/fail and recommendations; the “decision” is the final handoff (e.g. `docs/handoffs/frontend-YYYYMMDD.md`).
2. **Between domains:** Parent runs the **frontend trio** (or uses its last handoff), then the **backend trio**, then the **database trio**, then invokes a **cross-domain reviewer** subagent that receives all three “decisions” and produces the final “how the code should look” summary.

Below we define the agents and the handoff format so this workflow is explicit.

---

## Proposed Agent Roster

### 1. Frontend (3 subagents)

| Agent | Role | Responsibility |
|-------|------|----------------|
| **frontend-planner** | Plan | Scope UI/UX changes, accessibility, component boundaries, and what the frontend will consume from the API. Output: handoff doc (plan). |
| **frontend-developer** | Code | Implement HTML/CSS/JS in `web/` per plan and project rules. No TypeScript (per project). Output: code + short handoff for tester. |
| **frontend-tester** | Test | Verify behavior (manual steps or browser MCP), a11y basics, no secrets in console, clipboard/session behavior. Output: pass/fail + issues. |

### 2. Backend (3 subagents)

| Agent | Role | Responsibility |
|-------|------|----------------|
| **backend-planner** | Plan | API contracts, route design, auth/session, audit points, and integration with DB/crypto. Output: handoff doc (plan). |
| **backend-developer** | Code | Implement FastAPI routes, vault_db, crypto, config, audit in `src/vault/`. Thin handlers; logic in modules. Output: code + handoff for tester. |
| **backend-tester** | Test | Run API tests (e.g. pytest), check status codes and validation, no secrets in responses/logs. Output: pass/fail + issues. |

### 3. Database (3 subagents)

| Agent | Role | Responsibility |
|-------|------|----------------|
| **database-planner** | Plan | Schema changes, migrations, indexing, and what stays encrypted vs plain. Output: handoff doc (migration plan). |
| **database-developer** | Code | Write migrations under `migrations/`, update `vault_db.py` and any queries. Output: SQL + Python + handoff for tester. |
| **database-tester** | Test | Verify migrations apply cleanly, no data loss, encryption boundaries correct. Output: pass/fail + issues. |

### 4. Cross-domain and cross-cutting (4 subagents)

| Agent | Role | Responsibility |
|-------|------|----------------|
| **integration-reviewer** | Coordinate | Receives handoffs from frontend, backend, and database “trios.” Produces a single “decision” document: how the code should look, what’s done, what’s deferred, and any conflicts. Use after each domain trio has run. |
| **security-auditor** | Review | Audit crypto, auth, input validation, no hardcoded secrets, secure headers. Report by severity (Critical / High / Medium). |
| **verifier** | Verify | Independently confirm that claimed work is done: tests run and pass, features work end-to-end. Skeptical; run checks. |
| **documentation-educator** | Docs + teach | Keep HOW_IT_WORKS.md and EDUCATIONAL_CODE_WALKTHROUGH.md in sync with code; add teachable moments and “why” for changes. |

**Total: 13 subagents** (9 domain + 4 cross-cutting). You can start with 9 (plan/code/test per domain) and add the cross-cutting four as you need them.

---

## Handoff Format (So “Agreement” Is Explicit)

Each domain trio shares a **handoff document** so the next agent (or the integration-reviewer) has a single place to read “what was decided.”

Suggested location: `docs/handoffs/` (e.g. `frontend-20250203.md`, `backend-20250203.md`, `database-20250203.md`).

**Suggested structure for a handoff:**

```markdown
# Frontend handoff — YYYY-MM-DD

## Scope
- What was in scope (from planner).

## Decisions
- Key decisions (e.g. “no new dependencies,” “reuse existing api() in app.js”).

## Implemented
- Files changed; main behavior.

## Test results
- Pass/fail; open issues.

## Open / deferred
- What was not done and why.
```

The **integration-reviewer** reads all three domain handoffs and outputs:

- One “Master decision” doc: aligned approach, any cross-domain conflicts, and final “how the code should look” summary.

---

## How the Parent Agent Uses This

You (or the main Agent) can:

1. **Single-domain flow:**  
   “Implement the new ‘Create folder’ UI. Use the frontend trio: run frontend-planner, then frontend-developer with its output, then frontend-tester. Write the handoff to `docs/handoffs/frontend-YYYYMMDD.md`.”

2. **Cross-domain flow:**  
   “Add recovery key (backend + database + minimal UI). Run backend-planner, backend-developer, backend-tester; then database-planner, database-developer, database-tester; then frontend-developer for the one screen. Then run integration-reviewer with all handoffs and produce the master decision doc.”

3. **Explicit invocation:**  
   “/security-auditor review `src/vault/crypto.py` and `src/vault/api/main.py`.”  
   “/verifier confirm that unlock → add entry → lock works end-to-end.”

The **orchestration rule** (below) in `.cursor/rules/` tells the main Agent to use these subagents and handoffs when you ask for multi-step or cross-domain work.

---

## Suggested Additions to `.cursor/`

### A. Rules (`.cursor/rules/`)

| File | Purpose | When it applies |
|------|---------|------------------|
| `project-context.mdc` | (existing) Key facts, environment, practices. | Always. |
| `orchestration.mdc` | When to use which subagents; handoff paths; sequential order (plan → code → test) per domain; when to call integration-reviewer. | Always (or when you’re doing “agent workflows”). |
| `frontend-standards.mdc` | Plain JS only; no secrets in console; sessionStorage for session; 30s clipboard clear; a11y basics; file glob `web/**`. | When editing `web/*`. |
| `backend-standards.mdc` | FastAPI thin handlers; logic in vault_db/crypto/audit; env config; no secrets in logs; file glob `src/vault/**`. | When editing `src/vault/**`. |
| `database-standards.mdc` | Migrations in `migrations/`; application-level encryption; BLOB for sensitive fields; file glob `migrations/**`, `**/vault_db.py`. | When editing DB code. |
| `security.mdc` | Crypto (Argon2id, AES-256-GCM), constant-time compare, no hardcoded secrets; audit events; file glob `**/*.py`, `web/**`. | When touching auth/crypto/API. |
| `testing.mdc` | Run tests before marking done; pytest for API; structure of tests; file glob `**/test_*.py`, `**/*_test.py`. | When writing or running tests. |
| `documentation.mdc` | Update HOW_IT_WORKS.md and EDUCATIONAL_CODE_WALKTHROUGH.md with changes; teachable moments; file glob `**/*.md`, `**/*.py`. | When changing behavior or adding features. |

### B. Agents (`.cursor/agents/`)

All agents listed above live here as `name.md` with YAML frontmatter (`name`, `description`, optional `model`, `readonly`). Descriptions should be specific so the main Agent (or you) knows when to invoke them.

### C. Optional: Skills (`.cursor/` or user-level)

- **Run tests:** “Run pytest for this project and report pass/fail.”
- **Update docs:** “Update HOW_IT_WORKS.md and EDUCATIONAL_CODE_WALKTHROUGH.md for the last change.”
- **Security checklist:** “Run through security checklist (crypto, auth, no secrets in logs).”

These can be Cursor **skills** (single-purpose, repeatable) or spelled out in `orchestration.mdc` so the Agent runs the right subagents.

### D. Hooks (optional, if you use Cursor hooks)

- On subagent completion: append a one-line summary to a `docs/agent-runs.log` or copy handoff path into a “last handoff” file so the next agent knows what to read.

---

## 20+ Questions to Further Build Out Your Request

Use these to tune the roster, rules, and workflows.

### Scope and boundaries

1. Do you want **all 13 agents** from the start, or start with **9** (plan/code/test per domain) and add integration-reviewer, security-auditor, verifier, and documentation-educator later?
- **Clarification:** “9” = the **nine domain agents only**: frontend-planner, frontend-developer, frontend-tester, backend-planner, backend-developer, backend-tester, database-planner, database-developer, database-tester. The other **4** are cross-cutting: integration-reviewer, security-auditor, verifier, documentation-educator. So the choice is: use all 13 from the start, or start with just the 9 domain agents and add the 4 later.
- **Your answer (pending):** See follow-up question 1 below.

2. Should **frontend-tester** be allowed to run the app in a browser (MCP), or only reason about code and suggest manual steps?
yes, **frontend-tester** can use a browser, then close when tests are over. and reopen if/when needed again.

3. Should **backend-tester** and **database-tester** be **readonly** (`readonly: true`) so they never edit code, only run tests and report?
if code refactors are required, suggested, run questions back to the top for answers in order to continue.

4. Do you want a **separate “educator” agent** that only explains code to you (no edits), or is documentation-educator enough (docs + teachable moments)?
at this point, i think we can negate education as i just want the application in some version of completion.

5. Should the **integration-reviewer** run only after **all three** domain trios have produced handoffs, or can it run after a single domain (e.g. “review frontend handoff only”)?
**integration-reviewer** kicks in once all three domain trios have completed their parts. if bugs are detected, run them back up to the top agent who will ask me for guidance, then i will reassign tasks to agents 

### Workflow and handoffs

6. Where should handoff files live: **`docs/handoffs/`** (as above), or a different path (e.g. `.cursor/handoffs/` or a timestamped folder)?
**docs/handoffs** is fine. as long as once a handoff is initiated, it invokes the next agent to begin working, and so forth and so on

7. Should handoffs be **git-committed** so you have a history of “decisions,” or kept local/ignored?
- **Your answer:** Keep handoffs local. At the completion of integral steps, main Agent should ask you whether a git commit is desired.

8. When you say “when they come to an agreement” — do you prefer **sequential** (planner → developer → tester) so “agreement” is the tester’s sign-off, or **parallel** (all three run, parent synthesizes)? Sequential is easier to implement with current Cursor behavior.
**sequential** is fine

9. Do you want the **main Agent** to **always** run the full trio (plan → code → test) for a domain when you ask for a feature, or only when you explicitly say “use the frontend trio”?
- **Your answer:** Main Agent runs (e.g. a domain trio) only after you give permission.
10. Should **integration-reviewer** produce a **single “master” handoff** per task (e.g. `docs/handoffs/master-YYYYMMDD.md`) that summarizes all three domains?
yes

### Domain-specific

11. **Frontend:** Any extra constraints (e.g. no frameworks, or allow a specific one later)? Any a11y standard (WCAG 2.1 AA)?
wcag 2.1 aa standard is fine. if extra frameworks or specifics are suggested to enhance the app, send the questions all the way back up and i will answer

12. **Backend:** Should backend-planner always consider **audit events** and **session timeout** for every feature?
yes

13. **Database:** Should every schema change **require** a migration file and a rollback plan (e.g. down migration), or is “forward-only” enough for now?
use industry standard practices

14. Should **database-tester** run against a **test DB** (e.g. `vault_test.db`) only, never against your real vault DB?
as long as the test does not make changes to the real vault db, you can run tests. if failures are detected, run them up to me for further guidance

### Security and verification

15. Should **security-auditor** run **proactively** on every PR or major change (via description “use proactively when…”), or only when you invoke it with `/security-auditor`?
in order to understand this process, every PR, reach up to me to answer after explaining whats going on. after a few of these instances, i will be able to answer whether or not future audits can be run automatically without my approval

16. Do you want **verifier** to run **after** every “task complete” (e.g. “verifier confirm this is done”) as a standard step?
yes

17. Should **security-auditor** be **readonly** so it never suggests edits, only reports findings?
yes

### Documentation and education

18. Should **documentation-educator** run **after** every feature (update HOW_IT_WORKS + EDUCATIONAL_CODE_WALKTHROUGH), or only when you ask?
- **Your answer:** After every feature. (See follow-up: limit scope to HOW_IT_WORKS + glossary until “completion” if education is deprioritized.)

19. Do you want a **glossary** or **vocabulary** section maintained (e.g. in EDUCATIONAL_CODE_WALKTHROUGH or a separate VOCAB.md) and updated by the educator agent?
- **Your answer:** Yes. (See follow-up: where it should live.)

20. Should teachable moments be **inline in code comments**, in **EDUCATIONAL_CODE_WALKTHROUGH.md** only, or both?
- **Your answer:** Skip teachable moments from here on.

### Performance and cost

21. For **plan** and **test** agents, do you prefer **faster/cheaper model** (`model: fast`) to save tokens, and reserve the default model for **developers**?
no. as more tokens are needed, i will assess cost at that time. are there any other suggestions to decrease token cost?

22. Should any subagents run in **background** (`is_background: true`) so you get the main chat back immediately (e.g. long test runs or doc generation)?
no

### Tool and environment

23. Should **backend-tester** and **database-tester** be instructed to run in the project **venv** and use specific commands (e.g. `pytest`, `python -m vault.api.main`)?
perform just above industry standard testing

24. Do you want **explicit “contracts”** between frontend and backend (e.g. an OpenAPI snippet or a short “API contract” section in handoffs) so frontend-planner and backend-planner stay aligned?
- **Your answer:** Asked for layman rephrase; see “Follow-up questions” below.

25. Should we add a **.cursor/agents/README.md** that lists all agents, when to use them, and the recommended order (plan → code → test, then integration-reviewer)?
- **Your answer:** Yes. You asked: will this README keep agents on task and in order? **Answer:** The README is a reference for you and the main Agent (which agents exist, recommended order). It does not run agents by itself. The main Agent and the orchestration rule keep the process in order by following that order when you give permission.

---

## Follow-up questions (based on your answers)

Answer these so we can lock in behavior and update the agents/rules.

### Scope and workflow

**F1.** Now that “9” is defined (nine domain agents only; four cross-cutting are integration-reviewer, security-auditor, verifier, documentation-educator): do you want **all 13 agents from the start**, or **start with the 9 domain agents** and add the 4 cross-cutting when you need them?
use all 13 agents as they are intended


**F2.** When you say the main Agent runs “after permission is provided” — do you want it to **explicitly ask** before starting a trio (e.g. “I’ll run the frontend trio for ‘Create folder.’ Proceed?”), or is it enough that you asked for the feature and the Agent only runs when you say something like “yes, go ahead” or “run it”?
explicitly ask me so that hallucinations and unwanted actions are kept to as close to zero as possible

**F3.** Handoffs “invoke the next agent”: in Cursor the main Agent has to start each subagent. So “handoff invokes next agent” means: **you give one instruction** (e.g. “add Create folder UI using the frontend trio”), the main Agent runs planner → then developer (with the plan) → then tester (with the developer output) in one go, without you saying “now run developer” each time. Is that what you want?
for now, we can continue with this process. if i feel the need, i will amend this instruction later

**F4.** At which **integral steps** should the main Agent ask you “Do you want to git commit?” — after each domain trio, after integration-reviewer, after each full feature (all trios + integration-reviewer), or something else?
after each domain trio. i will either answer yes, or no. but keep asking

### Testers and refactors

**F5.** When **backend-tester** or **database-tester** says a code refactor is needed, should the main Agent (a) **present you the suggestion** and wait for your yes/no before any agent edits code, or (b) **automatically re-invoke the planner** for that domain with “refactor needed” and then run developer again after you approve the new plan?
wait for me

**F6.** For **database-tester**: you said tests must not change the real vault DB. To be safe, should we **always** use a separate test DB (e.g. `vault_test.db` or a temp file) so the real vault is never touched, even for reads? (That way a bug in a test never risks your real data.)
tests that only read the main DB are fine. if changes are needed. consult me

### Bugs and reassignment

**F7.** When **integration-reviewer** finds bugs and “runs them back to the top”: should the main Agent give you a **short menu** (e.g. “Re-run: frontend trio / backend trio / database trio / single agent X”) so you can pick what to re-run, or do you prefer to **answer in your own words** (e.g. “have frontend-developer fix the login button”) and have the Agent interpret that?
answer in my own words

### Documentation and education

**F8.** You said “negate education for now” and “skip teachable moments.” Should **documentation-educator** still run “after every feature” but **only** update **HOW_IT_WORKS.md** (user steps) and the **glossary**, and **not** maintain EDUCATIONAL_CODE_WALKTHROUGH or teachable moments until you say the app is in “some version of completion”?
correct

**F9.** Where should the **glossary** live: a new **VOCAB.md**, a section inside **HOW_IT_WORKS.md**, or a section inside **EDUCATIONAL_CODE_WALKTHROUGH.md** (even if we’re not updating the rest of that doc for now)?
separate VOCAB doc

### Security and PRs

**F10.** For the “learning phase” on security-auditor (you’ll decide after a few PRs whether to make it automatic): should the main Agent **(a)** before running security-auditor, say “This is a PR for [X]. Running security-auditor is recommended. Proceed?” or **(b)** run security-auditor and then show you the report and ask “Should future PRs run this automatically?”
- **Your answer:** **(a)** — Main Agent asks first; you say yes or no, then it runs or doesn't.

### Frontend and database

**F11.** **Frontend:** Any exception for very small, zero-dependency helpers (e.g. a tiny a11y utility that’s just a few lines), or should **any** new library/framework always be sent to you for approval?
always send for approval

**F12.** **Database:** “Industry standard” for migrations often means either (a) **forward-only** (new migration files only; rollback = restore from backup or a new “revert” migration) or (b) **up + down** (each migration has a “down” script). Which do you want for this project: **forward-only**, or **up + down** when possible?
up + down when possible

### API “contract” (Q24 in layman’s terms)

**F13.** Do you want the **frontend and backend to share a written “contract”**? That would be a short document (or section in handoffs) that says exactly what the API will send and receive — for example: “Create folder: send POST to /folders with body `{ "name": "Shopping" }`, response is `{ "id": 2 }`.” So when the frontend agents and backend agents work, they both follow the same list and don’t assume different things. Do you want that written contract (yes), or is it enough that the planner handoffs describe the API in words (no separate contract)?
written contract

### Process and cost

**F14.** Should we add a **small status note** (e.g. in `docs/handoffs/README.md` or a `docs/agent-status.md` file) that the main Agent updates after big steps (e.g. “Last: frontend-tester completed 2025-02-03; next: backend-planner”) so you can see at a glance where the workflow is?
yes

**F15.** **Token cost:** Besides using a faster model for some agents (you said you’ll assess later), other ways to reduce cost: **(a)** keep handoffs short and focused; **(b)** run verifier only on the critical path (e.g. before integration-reviewer) instead of after every small change; **(c)** have planners and testers output only what the next agent needs. Do you want the orchestration rule to mention any of these (e.g. “prefer short handoffs”)?
use **a** **b** and **c** to assist with cost savings

**F16.** **Testing:** Do you have (or want) a **standard test layout** and command — e.g. a `tests/` directory and “run `pytest tests/` from repo root with venv” — so backend-tester and database-tester always use the same approach?
- **Your answer:** **yes** — Define a standard: `tests/` directory, run `pytest tests/` from repo root with venv.

---

## Decisions summary (all follow-ups locked in)

| Ref | Decision |
|-----|----------|
| F1 | Use all 13 agents from the start. |
| F2 | Main Agent explicitly asks ("Proceed?") before starting a trio. |
| F3 | One instruction → Agent runs planner → developer → tester in one go (can amend later). |
| F4 | Ask "Do you want to git commit?" after each domain trio; keep asking. |
| F5 | If tester says refactor needed: present to user and wait; no auto re-invoke. |
| F6 | Tests that only read main DB are fine; if changes needed, consult user. |
| F7 | User answers in own words for reassignment (no menu). |
| F8 | documentation-educator: only HOW_IT_WORKS.md + glossary until "completion." |
| F9 | Glossary in separate **VOCAB.md**. |
| F10 | **(a)** Main Agent asks first before running security-auditor. |
| F11 | Any new frontend library/framework → always send for approval. |
| F12 | Migrations: **up + down** when possible. |
| F13 | Written API contract (frontend/backend). |
| F14 | Yes — status note updated after big steps (e.g. docs/agent-status.md). |
| F15 | Orchestration mentions (a) short handoffs, (b) verifier on critical path, (c) planners/testers output only what next agent needs. |
| F16 | **yes** — Define standard: `tests/` directory, `pytest tests/` from repo root with venv. |

---

## Next Steps

1. **Answer** the questions above (or the subset that matter most to you).
2. **Create** `.cursor/agents/` and add the agent `.md` files (I can generate starter content for each).
3. **Add** the new rules (orchestration, frontend/backend/database/security/testing/documentation) to `.cursor/rules/`.
4. **Optionally** add `docs/handoffs/` and a short note in `orchestration.mdc` on handoff paths and when to run integration-reviewer.

If you tell me which agents you want first (e.g. “all 13” or “only the 9 domain agents”) and your preferences on the questions that matter most (e.g. handoff location, readonly testers, model for plan/test), I can generate the exact agent files and rule snippets next.
