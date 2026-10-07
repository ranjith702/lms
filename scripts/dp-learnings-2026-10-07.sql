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
