# Bug & Error Log — Library Management System

Every error hit while building, how it was found, the root cause, and the fix.
Also stored in the DevPilot `learnings` table (`project = 'library-m-system'`).

| ID | Date | Area | Severity | Status |
|----|------|------|----------|--------|
| LMS-BUG-001 | 2026-10-07 | Setup / Alembic CLI | low | fixed |
| LMS-BUG-002 | 2026-10-07 | Config / env vars | **high** | fixed |
| LMS-BUG-003 | 2026-10-07 | Assistant search | low | fixed |
| LMS-BUG-004 | 2026-10-07 | Assistant search SQL | medium | fixed |
| LMS-BUG-005 | 2026-10-07 | Tests (recommendations) | low | fixed |
| LMS-BUG-006 | 2026-10-07 | Loans (race condition) | **high** | fixed |
| LMS-BUG-007 | 2026-10-07 | Docker / DB exposure | medium | fixed |
| LMS-BUG-008 | 2026-10-07 | Seed data (book title) | low | fixed |
| LMS-BUG-009 | 2026-10-07 | Recommendation reason text | low | fixed |
| LMS-BUG-010 | 2026-10-07 | Frontend crash when an API call fails | **high** | fixed |
| LMS-BUG-011 | 2026-10-07 | AI answer quality (markdown, noise, invented services) | medium | fixed |

---

## LMS-BUG-001 — `alembic init -q` rejected
- **Error:** `alembic: error: unrecognized arguments: -q`
- **Root cause:** `alembic init` has no quiet flag; I assumed one.
- **Fix:** ran `alembic init alembic` and silenced output with `>/dev/null`.
- **Lesson:** check `--help` before assuming a CLI flag exists.

## LMS-BUG-002 — App config picked up ANOTHER project's database (high)
- **Error:** `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres`
- **How found:** the dialect name `postgres` didn't match our `.env` (`postgresql+psycopg://...`).
  Checked the shell environment: a machine-wide `DATABASE_URL` pointed at the DevPilot database (port 5499).
- **Root cause:** pydantic-settings gives **real environment variables priority over `.env`**.
  Our setting was called `DATABASE_URL`, so the machine-wide one won.
  Alembic would have created our tables inside the DevPilot database. It was saved only because the
  old `postgres://` URL spelling isn't accepted by SQLAlchemy 2.
- **Fix:** every app setting now has an `LMS_` prefix (`env_prefix="LMS_"` in `app/config.py`, and
  `LMS_DATABASE_URL` etc. in `.env`). Another project's variables can no longer leak in.
  Tests also `assert "lms_test" in TEST_URL` before touching anything.
- **Lesson:** give app env vars a project prefix; never use bare `DATABASE_URL` on a dev
  machine that runs several projects.

## LMS-BUG-003 — Placeholder code left in `search_books`
- **Error:** no runtime error yet; the first draft contained an unused `if False` expression and a helper
  defined below its use.
- **How found:** reading back my own code before running it.
- **Fix:** rewrote the function cleanly.
- **Lesson:** reread every file once before running the tests.

## LMS-BUG-004 — `literal_column(":q")` bind params never bound
- **Error:** `psycopg.errors.SyntaxError: syntax error at or near ":"` at `to_tsquery('english', :q)`
- **Root cause:** `literal_column()` inserts raw SQL text, so SQLAlchemy does **not** parse `:name`
  placeholders inside it. The literal `:q` reached Postgres, which uses `%s`-style parameters.
- **Fix:** built the score from SQLAlchemy expressions instead:
  `func.ts_rank(Book.search, func.to_tsquery('english', q))` + `sum(cast(Book.tags.any(w), Integer))`.
  Every value is now a bound parameter, which also prevents SQL injection.
- **Lesson:** use `text()` (which parses `:name`) or SQLAlchemy expressions; never `literal_column` with
  parameters.

## LMS-BUG-005 — Recommendation test expected a book in two sections
- **Error:** `assert 'Foundation' in ['I, Robot']`, then `assert 'SPQR' in []`
- **Root cause:** a bug in the test, not the code. By design a book appears in only one section (the
  first that claims it), so the UI never shows duplicates. The fixture's books matched several sections.
- **Fix:** the test now asserts there are no duplicates. It uses a fixture book with no shared tags (Odes),
  so only the "also borrowed" rule can find it.
- **Lesson:** when a test fails, first decide whether the code or the test's expectation is wrong.

## LMS-BUG-006 — One student could exceed the 3-book limit with parallel requests (high)
- **How found:** automated security review of commit `bc8f2a1` flagged `loan_service.py`; I wrote a test that
  fires 8 borrow requests for 8 different books from the same student at once.
- **Error reproduced:** `assert 8 == 3`, so all 8 borrows succeeded.
- **Root cause:** check-then-act race. Each request counted active loans (0, 1, 2...) before any other request
  committed, so every one passed the limit check. The atomic copy decrement only protects a single *book*,
  not one *student's* total.
- **Fix:** `SELECT ... FROM users WHERE id = :me FOR UPDATE` at the start of `borrow()`. One student's
  borrow requests now queue up, while different students still borrow in parallel.
  Test `test_concurrent_borrows_by_one_student_respect_loan_limit` passes on repeated runs.
- **Lesson:** every "count, then insert" rule needs a lock, or a database constraint, for the thing being counted.

## LMS-BUG-007 — Postgres exposed on all network interfaces with a default password
- **How found:** same security review (`docker-compose.yml`).
- **Root cause:** `ports: "5433:5432"` binds `0.0.0.0`, so anyone on the same Wi-Fi could connect.
  `${POSTGRES_PASSWORD:-lms_dev_password}` meant it also worked with a well-known password.
- **Fix:** bind `127.0.0.1:5433:5432`. Use `${POSTGRES_PASSWORD:?...}` so compose refuses to start without a
  password from `.env` (verified: `docker compose config` fails with no password).
- **Lesson:** publish dev databases on localhost only; never ship a fallback password.

## LMS-BUG-008 — Wrong book title in seed data
- **How found:** proofreading the seed output.
- **Root cause:** my typo. Premchand's novel is *Godaan*, not "The Godan".
- **Fix:** corrected `scripts/seed.py`, and `UPDATE books ... RETURNING` confirmed 1 row changed in the live DB.
- **Lesson:** proofread real-world facts in seed/demo data; it is user-visible.

## LMS-BUG-009 — Author names lowercased in recommendation reasons
- **Error seen in the UI:** "More by agatha christie" (browser screenshot of a student profile).
- **Root cause:** Python's `str.capitalize()` upper-cases the first letter **and lowercases all the others**.
- **Fix:** `reason[:1].upper() + reason[1:]`. Regression test `test_reason_keeps_author_name_casing` failed first, then
  passed. The live API now returns "More by Isaac Asimov".
- **Extra lesson:** after the fix, the browser *still* showed lowercase because the API server was started
  without `--reload` and was running the old code. Always restart (or use `--reload`) before re-checking a fix.

## LMS-BUG-010 — Pages crashed when an API call failed (high)
- **Error (browser console):** `TypeError: Cannot read properties of null (reading 'books') at Desk`
- **How found:** while debugging browser tests, I read the console log instead of assuming the test was wrong.
- **Root cause:** pages rendered `loading ? <Loading/> : <use data>`. When a request *failed* (e.g. a session that
  expired mid-visit returns 401), `loading` is false **and** `data` is null, so the page dereferenced null.
  With no error boundary, React tore down the whole app. The same pattern was in 13 places.
- **Fix:** every one now renders `loading ? <Loading/> : !data ? null : ...` (the page's error message explains what
  happened), and an app-wide `ErrorBoundary` shows a recovery screen for any future render crash.
- **Verified:** logged in as the librarian, revoked the session server-side, opened the Desk, and it went back to the
  login page with 0 page errors and no crash screen.
- **Lesson:** "not loading" doesn't mean "has data". Handle loading, error and empty states separately.

## LMS-BUG-011 — First live RAG run exposed answer-quality problems
- **How found:** `python -m scripts.test_rag_live` against the real models (Nemotron embeddings + Claude Haiku 4.5).
- **Problems → fixes:**
  1. Claude used markdown (`**bold**`) despite "plain text" in the prompt → the prompt now *allows* only `**title**`
     and `- ` bullets, and `RichText.jsx` renders exactly those as React elements (never `innerHTML`).
  2. Keyword search added noise (*Frankenstein* for "stranded astronaut") → the books the answer names come first;
     the rest sit under "Other matches".
  3. With **0** books retrieved, Claude invented an "interlibrary loan" service → when nothing is retrieved the LLM is
     not called at all (also saves cost), and the prompt forbids promising library services.
  4. My injection check was wrong: it flagged an answer that *refused* the fake book → it now checks for prompt
     leaks and for actually recommending a non-catalog book.
- **Result:** live test 10/10 PASS (`test_results/rag/`).

---

## Testing notes (not app bugs, but worth knowing)
- **Browser-test misclicks:** my Playwright scripts landed on the wrong pages several times. Causes:
  (1) `getByRole('link', {name: 'Requests'})` matched two links, so use `exact: true` or scope to the nav;
  (2) clicking before the previous page finished rendering, so wait for the URL with `waitForURL`;
  (3) `networkidle` is unreliable with the Vite dev server, so wait for a real element instead;
  (4) aborted scripts kept driving the same tab. The `sessions` table showed an extra login I hadn't made.
  The app itself behaved correctly every time I checked by hand.
- **Mouse clicks stopped reaching the page** (Playwright MCP, later in a long session): a capture listener saw
  *zero* events, while a DOM `element.click()` navigated correctly and only one tab existed. It's a tool issue,
  not the app. Workaround: `locator.dispatchEvent('click')` + `press('Enter')`. Debugging it is what surfaced LMS-BUG-010.
- **"Page wider than the screen":** a full-page screenshot was 1846px wide, but `scrollWidth == clientWidth`
  showed no overflow. The test browser window was simply larger than the requested viewport.
