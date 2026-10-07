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
