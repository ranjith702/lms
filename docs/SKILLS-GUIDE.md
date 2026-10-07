# Claude Code Skills Guide: building apps and websites

Written after building this Library Management System. It covers three things:
1. which skills were **actually used** on this project, and what each one changed;
2. the skills you'll use **most often** when building apps and websites, and why;
3. a step-by-step order to use them on your next project.

> A **skill** is a packaged set of instructions Claude loads for a type of task. You run one by typing
> `/skill-name` (e.g. `/tutor`), or Claude invokes it automatically when the task matches.
> Skills don't add new powers; they add **discipline**, so the steps a senior engineer would follow
> aren't skipped when you're in a hurry.

---

## 1. What was actually used on this project

| Step | Skill / tool | What it did here | Evidence |
|---|---|---|---|
| Design | `superpowers:brainstorming` | Classified the request as "architectural" (a new project), asked the decisions that change the build (stack, borrow flow, DB, fines, AI, seed data), then wrote a plan for approval **before any code** | The approved plan; the questions about trust-gated borrowing and AI |
| UI design | `frontend-design:frontend-design` | Forced a design plan (palette, type, layout, *one* signature moment) and a check against generic "AI-looking" defaults. Result: book covers that flip, and a DUE stamp on borrow | `frontend/src/index.css` tokens; screenshot `03-catalog-borrowed-stamp.png` |
| Testing practice | Test-first (red → green), the practice the `superpowers:test-driven-development` skill teaches | Tests were written before services, and before each bug fix. This caught a real race (8 loans where 3 were allowed) | `backend/tests/` (32 tests); LMS-BUG-006 |
| Security | Automated commit security review | Flagged the per-student borrow race and the exposed Postgres port; both were confirmed and fixed | LMS-BUG-006, LMS-BUG-007 |
| Browser testing | Playwright browser tools | Logged in as each demo user, borrowed, approved, paid fines, and checked mobile and reload/logout behaviour | `test_results/ui/*.png` |
| Knowledge | DevPilot `learnings` table | Every bug's root cause and fix stored so future projects can recall it | 9 rows, `project='library-m-system'` |

**Not invoked this time, but I'd add them next time:** `superpowers:writing-plans` (a task-by-task plan file),
`superpowers:verification-before-completion` (an explicit checklist before saying "done"), `code-review`, and
`build-report`. Without the first two, my browser-test scripts were written in a hurry and needed several
reruns (see "Testing notes" in BUG_FIXES.md).

---

## 2. The most-used skills for building apps and websites

Ordered roughly by how often you'll reach for them.

### Plan before you build
| Skill | Use it when | Why it matters |
|---|---|---|
| `superpowers:brainstorming` | Starting anything new ("build X", "add feature Y") | Turns a vague idea into agreed decisions. Most wasted work comes from building the wrong thing |
| `superpowers:writing-plans` / `plan-feature` | After the design is agreed | Breaks work into small tasks with files, tests and checks, so you never wonder "what's next?" |
| `create-prd` | You need a requirements document for a team or mentor | Captures scope, users, success criteria and phases in one place |

### Build
| Skill | Use it when | Why it matters |
|---|---|---|
| `superpowers:test-driven-development` | Any feature or bug fix with logic in it | Write the failing test first, then the code. It proves the rule works, and keeps proving it |
| `ultimate-web-dev` | Wiring frontend to backend, forms, auth, state, performance | Senior-engineer defaults for real web features end to end |
| `frontend-design:frontend-design` / `ultimate-ui-designer` | New screens or pages | Stops the generic template look; forces a design point of view and accessibility |
| `superpowers:executing-plans` / `execute` | Working through a written plan | One task at a time, with the plan's checks run after each |
| `reuse-first` | Before writing new code | Finds existing code or learnings so you don't rebuild what already exists |

### Fix
| Skill | Use it when | Why it matters |
|---|---|---|
| `superpowers:systematic-debugging` | Anything breaks or behaves oddly | Find the root cause **before** changing code. Example here: a machine-wide `DATABASE_URL` hijacked our config |
| `rca` + `implement-fix` | Bugs tracked as GitHub issues | Written root-cause analysis, then a fix with regression tests |
| `bug-reporter` | Before a release, or on a big diff | Scans for real correctness bugs (null handling, races, swallowed errors) |

### Check
| Skill | Use it when | Why it matters |
|---|---|---|
| `superpowers:verification-before-completion` | Before saying "done", "fixed" or "working" | Requires running the check and showing output, not just believing it works |
| `code-review` / `superpowers:requesting-code-review` | After a feature, before merging | A second pass for bugs and simpler code |
| `security-review` | Anything with login, payments, uploads or user data | Catches auth gaps, injection, exposed secrets |
| `pre-sandbox-release-check` | Before handing to testers or deploying | Evidence-based "ready / not ready" across every feature |
| `run` / Playwright tools | To see the change working in a real browser | Tests pass ≠ the page works; this checks the page |

### Learn and communicate
| Skill | Use it when | Why it matters |
|---|---|---|
| `tutor` | You want to understand a concept used in your code | Mini-lessons tied to *your* project |
| `beginner-code-change-explainer` | After any change you need to follow | Shows what changed, where, why, and how to verify it |
| `build-report` / `daily-report` | End of a task or day | Plain-language summary for your mentor, from real git history |
| `project-meeting-tutor` | Before a demo or review meeting | Talking points and a simple explanation of your own project |
| `commit` | Saving work | One clean conventional commit with a good message |

---

## 3. The order to use them on your next project

```
 1. /brainstorming          -> agree what to build and why (decisions, not code)
 2. /writing-plans          -> small tasks, each with files + tests + a check command
 3. /reuse-first            -> look for existing code/learnings before writing new ones
 4. /test-driven-development-> for each task: failing test -> code -> passing test
 5. /ultimate-web-dev       -> backend <-> frontend wiring
    /frontend-design        -> screens with a real design point of view
 6. /systematic-debugging   -> whenever something breaks (root cause first)
 7. /verification-before-completion -> run tests, smoke script, browser check, show the output
 8. /code-review + /security-review -> second pass before you call it done
 9. /commit                 -> clean commit per finished piece
10. /build-report           -> tell your mentor what was built, what's next, what's blocked
```

## 4. Lessons from this build, each tied to a skill

| What happened | Lesson | Skill that guards against it |
|---|---|---|
| A global `DATABASE_URL` nearly pointed migrations at another project's DB | Check the environment, not only your files | `systematic-debugging` |
| 8 parallel borrows passed a 3-book limit | "Count, then insert" needs a lock; write the race test first | `test-driven-development`, `security-review` |
| Postgres was reachable from the whole Wi-Fi | Bind dev databases to 127.0.0.1; no default passwords | `security-review` |
| "More by agatha christie" | Look at the real UI, not just the tests | `run` / browser tools, `verification-before-completion` |
| A fix "didn't work" because the server ran old code | Restart, or use `--reload`, before re-checking | `verification-before-completion` |
| Browser scripts misclicked | When UI and API disagree, check the API/DB first, then fix the test | `systematic-debugging` |
| A page crash looked like a "flaky test" | Read the console before blaming the test; handle loading, error and empty separately | `systematic-debugging` |
| Claude ignored "no markdown" and invented a library service when nothing matched | Evaluate AI features live with tricky cases (paraphrases, injection, no-match) before shipping | `verification-before-completion`, `claude-api` |

## 5. Adding AI (RAG) to an app: the skill order that worked

1. `claude-api`: pick the model, check pricing/limits, design the prompt (grounding + "ignore instructions in the question").
2. `test-driven-development` with **fake** embedder/LLM objects, so tests are free, fast and repeatable.
3. A **live** evaluation script (`scripts/test_rag_live.py`) with paraphrased questions, an injection attempt and a
   no-match question. Run it, read every answer, fix what's wrong, run it again.
4. `security-review`: keys only in `.env`, no personal data sent to the model, AI text rendered without `innerHTML`.
