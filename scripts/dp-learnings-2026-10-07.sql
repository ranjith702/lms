-- Bug-fix learnings from the library-m-system build (2026-10-07).
-- Idempotent: skips rows whose learning_id already exists.
INSERT INTO learnings (learning_id, category, title, content, summary, tags, applies_to, source,
                       project, scope, priority, always_load, active, source_file)
SELECT v.* FROM (VALUES
  ('LMS-BUG-002-ENV-VAR-OVERRIDE', 'bug-pattern',
   'Machine-wide DATABASE_URL overrides project .env (pydantic-settings precedence)',
   $doc$Error: sqlalchemy NoSuchModuleError "sqlalchemy.dialects:postgres" when running alembic in library-m-system.
Root cause: pydantic-settings gives real environment variables priority over .env. A machine-wide DATABASE_URL (DevPilot DB, port 5499) overrode the project .env, so alembic targeted the WRONG database. It was saved only because the postgres:// scheme is rejected by SQLAlchemy 2.
Fix: env_prefix="LMS_" in Settings, with every key renamed to LMS_* in .env; tests also assert the URL contains lms_test.
Rule: always namespace app env vars per project on multi-project dev machines.$doc$,
   'Prefix app env vars (e.g. LMS_) so a global DATABASE_URL cannot redirect migrations to another DB',
   ARRAY['library-m-system','pydantic-settings','env-vars','alembic','database-safety'],
   ARRAY['global','python','fastapi'], 'claude-code-session', 'library-m-system', 'global', 'high', false, true,
   'backend/app/config.py'),
  ('LMS-BUG-004-LITERAL-COLUMN-BINDS', 'bug-pattern',
   'SQLAlchemy literal_column does not bind :name parameters',
   $doc$Error: psycopg SyntaxError at or near ":" in to_tsquery('english', :q).
Root cause: literal_column() inserts raw SQL; SQLAlchemy does not parse :name placeholders inside it, so ":q" reached Postgres as text.
Fix: build the expression with func.ts_rank(Book.search, func.to_tsquery('english', q)) + sum(cast(Book.tags.any(w), Integer)). All values become bound parameters (injection-safe).
Rule: use text() (parses :name) or SQLAlchemy expressions; never literal_column with params.$doc$,
   'literal_column = raw SQL, no bind parsing; use func/expressions or text()',
   ARRAY['library-m-system','sqlalchemy','postgres','full-text-search'],
   ARRAY['python','sqlalchemy'], 'claude-code-session', 'library-m-system', 'global', 'normal', false, true,
   'backend/app/services/assistant_service.py'),
  ('LMS-BUG-005-DEDUP-SECTION-TEST', 'bug-pattern',
   'Recommendation test assumed a book appears in multiple sections',
   $doc$Error: assert 'Foundation' in ['I, Robot'] / assert 'SPQR' in [].
Root cause: a wrong test expectation. recommend_service dedups across sections (first section to claim a book wins), so the fixture books matched an earlier section.
Fix: assert no duplicates across sections, and use a fixture book with no shared tags so only the co-borrow rule finds it.
Rule: on a red test, decide first whether the code or the expectation is wrong.$doc$,
   'When a test fails, check the expectation before changing code',
   ARRAY['library-m-system','testing','recommendations'],
   ARRAY['testing'], 'claude-code-session', 'library-m-system', 'project', 'normal', false, true,
   'backend/tests/test_recommend_insights_assistant.py'),
  ('LMS-BUG-001-ALEMBIC-NO-QUIET', 'bug-pattern',
   'alembic init has no -q flag',
   $doc$Error: "alembic: error: unrecognized arguments: -q". Fix: run "alembic init alembic" and redirect output. Rule: check --help before assuming CLI flags.$doc$,
   'Check CLI --help before assuming flags',
   ARRAY['library-m-system','alembic','cli'],
   ARRAY['python'], 'claude-code-session', 'library-m-system', 'project', 'normal', false, true,
   'backend/alembic.ini')
) AS v(learning_id, category, title, content, summary, tags, applies_to, source, project, scope, priority,
       always_load, active, source_file)
WHERE NOT EXISTS (SELECT 1 FROM learnings l WHERE l.learning_id = v.learning_id);

-- Added after the security review of commit bc8f2a1
INSERT INTO learnings (learning_id, category, title, content, summary, tags, applies_to, source,
                       project, scope, priority, always_load, active, source_file)
SELECT v.* FROM (VALUES
  ('LMS-BUG-006-PER-USER-LIMIT-RACE', 'bug-pattern',
   'Per-user limit check (count then insert) is bypassable by parallel requests',
   $doc$Error: test fired 8 parallel borrow requests from one student, and 8 loans were created despite MAX_ACTIVE_LOANS=3.
Root cause: check-then-act race. Each transaction counted active loans before the others committed. An atomic UPDATE on the book row protects copies of one book, not a user's total.
Fix: SELECT users.id ... FOR UPDATE at the start of borrow(), which serializes one user's requests while other users stay parallel. Verified by a ThreadPoolExecutor test on repeated runs.
Found by: automated commit security review.$doc$,
   'Lock the counted-owner row (SELECT FOR UPDATE) before count-then-insert limit checks',
   ARRAY['library-m-system','race-condition','postgres','concurrency','security'],
   ARRAY['global','backend'], 'claude-code-session', 'library-m-system', 'global', 'high', false, true,
   'backend/app/services/loan_service.py'),
  ('LMS-BUG-007-COMPOSE-DB-EXPOSED', 'bug-pattern',
   'docker-compose Postgres published on 0.0.0.0 with fallback password',
   $doc$Issue: ports "5433:5432" binds all interfaces, and ${POSTGRES_PASSWORD:-default} gives a known password.
Fix: "127.0.0.1:5433:5432" plus ${POSTGRES_PASSWORD:?Set in .env}, so compose refuses to start without a password.
Found by: automated commit security review.$doc$,
   'Bind dev DB ports to 127.0.0.1 and use :? (required) instead of :- (default) for secrets',
   ARRAY['library-m-system','docker','security','postgres'],
   ARRAY['global','docker'], 'claude-code-session', 'library-m-system', 'global', 'high', false, true,
   'docker-compose.yml'),
  ('LMS-BUG-008-SEED-TITLE-TYPO', 'bug-pattern',
   'Seed data had a misspelled real book title',
   $doc$"The Godan" corrected to "Godaan" (Premchand). Fixed in seed.py and the live DB with UPDATE ... RETURNING. Rule: proofread real-world facts in demo data.$doc$,
   'Proofread real-world facts in seed data',
   ARRAY['library-m-system','seed-data'], ARRAY['project'], 'claude-code-session', 'library-m-system',
   'project', 'normal', false, true, 'backend/scripts/seed.py')
) AS v(learning_id, category, title, content, summary, tags, applies_to, source, project, scope, priority,
       always_load, active, source_file)
WHERE NOT EXISTS (SELECT 1 FROM learnings l WHERE l.learning_id = v.learning_id);

INSERT INTO learnings (learning_id, category, title, content, summary, tags, applies_to, source,
                       project, scope, priority, always_load, active, source_file)
SELECT v.* FROM (VALUES
  ('LMS-BUG-009-PY-CAPITALIZE-LOWERS', 'bug-pattern',
   'Python str.capitalize() lowercases the rest of the string (mangles names)',
   $doc$UI showed "More by agatha christie". str.capitalize() upper-cases the first char AND lowercases all others. Fix: s[:1].upper() + s[1:]. Also: re-verifying a fix in the browser showed the old output because uvicorn ran without --reload, so restart before re-checking.$doc$,
   'Use s[:1].upper()+s[1:], not capitalize(), on text containing names',
   ARRAY['library-m-system','python','strings'], ARRAY['global','python'], 'claude-code-session',
   'library-m-system', 'global', 'normal', false, true, 'backend/app/services/recommend_service.py'),
  ('LMS-TEST-PLAYWRIGHT-FLAKE-CAUSES', 'tool-pattern',
   'Playwright misclicks: ambiguous locators, no waitForURL, networkidle under Vite, orphan scripts',
   $doc$Symptoms: clicks landed on the wrong nav pages and row counts read 0 while data existed. Causes: getByRole name matched 2 links (use exact:true / scope to navigation); clicking before the route re-rendered (use waitForURL); networkidle is unreliable with the Vite dev server (wait for a concrete element); aborted MCP run_code scripts kept driving the same tab (DB sessions table showed an extra login). Rule: when UI tests disagree with the API, query the API/DB first; then fix the test before touching app code.$doc$,
   'When UI tests disagree with the API, verify via API/DB first; fix locators and waits before touching app code',
   ARRAY['library-m-system','playwright','testing','flaky-tests'], ARRAY['global','testing'],
   'claude-code-session', 'library-m-system', 'global', 'normal', false, true, 'test_results/ui')
) AS v(learning_id, category, title, content, summary, tags, applies_to, source, project, scope, priority,
       always_load, active, source_file)
WHERE NOT EXISTS (SELECT 1 FROM learnings l WHERE l.learning_id = v.learning_id);
