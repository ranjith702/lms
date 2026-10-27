-- Backfill docs/BUG_FIXES.md (LMS-BUG-001..011) into DevPilot's bug tracker (sdlc_bugs), so the bugs are
-- searchable next to every other project's bugs (mentor review 2026-10-27).
-- All 11 were fixed on 2026-10-07, so they go in as status='fixed'. The insert triggers would open an active
-- fix pipeline and write a generic learning per bug; this transaction closes those pipelines and points each
-- bug at the curated learning from dp-learnings-2026-10-07.sql / -10-27.sql instead.
-- Idempotent: ON CONFLICT DO NOTHING + guarded UPDATEs. Run dp-learnings-2026-10-27.sql first.
BEGIN;

INSERT INTO sdlc_bugs (id, project_id, title, severity, priority, status, source_type, source_data, root_cause,
                       resolution, tags, reporter, env, created_at, resolved_at)
SELECT b.id, 'library-m-system', b.title, b.severity,
       CASE b.severity WHEN 'high' THEN 'high' WHEN 'low' THEN 'low' ELSE 'normal' END,
       'fixed', 'manual_audit', jsonb_build_object('backfilled_from', 'docs/BUG_FIXES.md', 'doc_id', b.doc_id),
       b.root_cause, b.resolution, ARRAY['library-m-system', lower(b.doc_id), 'backfill'], 'claude-code-session',
       'local', '2026-10-07 12:00+05:30', '2026-10-07 12:00+05:30'
FROM (VALUES
  ('BUG-LMS-001', 'LMS-BUG-001', 'low', '`alembic init -q` rejected: no such flag',
   'alembic init has no quiet flag; it was assumed.', 'Ran `alembic init alembic` with output sent to /dev/null.'),
  ('BUG-LMS-002', 'LMS-BUG-002', 'high', 'App config picked up another project''s DATABASE_URL',
   'pydantic-settings gives real environment variables priority over .env; a machine-wide DATABASE_URL (DevPilot DB) won, so alembic targeted the wrong database.',
   'env_prefix="LMS_" on every setting; tests assert the URL contains lms_test.'),
  ('BUG-LMS-003', 'LMS-BUG-003', 'low', 'Placeholder code left in search_books',
   'First draft contained an unused `if False` expression and a helper defined below its use.', 'Rewrote the function; found by rereading before running.'),
  ('BUG-LMS-004', 'LMS-BUG-004', 'medium', 'literal_column(":q") bind params never bound in search SQL',
   'literal_column inserts raw SQL, so SQLAlchemy does not parse :name placeholders; ":q" reached Postgres.',
   'Built the score from func.ts_rank / func.to_tsquery expressions; every value is a bound parameter.'),
  ('BUG-LMS-005', 'LMS-BUG-005', 'low', 'Recommendation test expected a book in two sections',
   'Wrong test expectation: a book appears only in the first section that claims it.', 'Test asserts no duplicates and uses a fixture book only one rule can find.'),
  ('BUG-LMS-006', 'LMS-BUG-006', 'high', 'One student could exceed the 3-book limit with parallel requests',
   'Check-then-act race: concurrent requests counted active loans before any committed.',
   'SELECT ... FROM users WHERE id = :me FOR UPDATE at the start of borrow(); concurrency test added.'),
  ('BUG-LMS-007', 'LMS-BUG-007', 'medium', 'Postgres exposed on all interfaces with a default password',
   'compose published 5433 on 0.0.0.0 with a fallback password.', 'Bind 127.0.0.1:5433; ${POSTGRES_PASSWORD:?} refuses to start without a password.'),
  ('BUG-LMS-008', 'LMS-BUG-008', 'low', 'Wrong book title in seed data ("The Godan")',
   'Typo in scripts/seed.py; the novel is Godaan.', 'Corrected the seed and the live row.'),
  ('BUG-LMS-009', 'LMS-BUG-009', 'low', 'Author names lowercased in recommendation reasons',
   'str.capitalize() lowercases everything after the first letter.', 'reason[:1].upper() + reason[1:]; regression test added.'),
  ('BUG-LMS-010', 'LMS-BUG-010', 'high', 'Pages crashed when an API call failed',
   'Pages rendered `loading ? <Loading/> : data.x`; a failed request leaves loading=false and data=null.',
   'Guarded 13 call sites with !data checks and added an app-wide ErrorBoundary.'),
  ('BUG-LMS-011', 'LMS-BUG-011', 'medium', 'First live RAG run exposed answer-quality problems',
   'Model ignored "no markdown", keyword noise ranked high, LLM invented a service when 0 books were retrieved.',
   'Allow minimal markdown rendered by RichText; named books first; skip the LLM on zero retrieval. Live test 10/10.')
) AS b(id, doc_id, severity, title, root_cause, resolution)
ON CONFLICT (id) DO NOTHING;

-- Already fixed: close the pipelines the insert trigger opened, so no fix sprint is ever planned for them.
UPDATE bug_pipeline_runs
SET stage = 'close', status = 'completed', completed_at = NOW(), updated_at = NOW(),
    stage_history = stage_history || jsonb_build_array(jsonb_build_object(
      'stage', 'close', 'entered_at', NOW()::text, 'note', 'backfill: fixed 2026-10-07, see docs/BUG_FIXES.md'))
WHERE bug_id LIKE 'BUG-LMS-%' AND status = 'active';

-- Link each bug to its curated learning and mark the pipeline done.
UPDATE sdlc_bugs b
SET pipeline_status = 'completed',
    learning_ids = ARRAY(SELECT l.id FROM learnings l WHERE l.learning_id = m.learning_id)
FROM (VALUES
  ('BUG-LMS-001', 'LMS-BUG-001-ALEMBIC-NO-QUIET'), ('BUG-LMS-002', 'LMS-BUG-002-ENV-VAR-OVERRIDE'),
  ('BUG-LMS-003', 'LMS-BUG-003-REREAD-BEFORE-RUN'), ('BUG-LMS-004', 'LMS-BUG-004-LITERAL-COLUMN-BINDS'),
  ('BUG-LMS-005', 'LMS-BUG-005-DEDUP-SECTION-TEST'), ('BUG-LMS-006', 'LMS-BUG-006-PER-USER-LIMIT-RACE'),
  ('BUG-LMS-007', 'LMS-BUG-007-COMPOSE-DB-EXPOSED'), ('BUG-LMS-008', 'LMS-BUG-008-SEED-TITLE-TYPO'),
  ('BUG-LMS-009', 'LMS-BUG-009-PY-CAPITALIZE-LOWERS'), ('BUG-LMS-010', 'LMS-BUG-010-NOT-LOADING-NOT-DATA'),
  ('BUG-LMS-011', 'LMS-RAG-LIVE-EVAL-FINDINGS')
) AS m(bug_id, learning_id)
WHERE b.id = m.bug_id AND b.pipeline_status IS DISTINCT FROM 'completed';

-- The insert trigger's generic one-line learnings duplicate the curated ones: keep them, but inactive.
UPDATE learnings
SET active = false, tags = array_append(tags, 'superseded-by-curated-lms-learning'), updated_at = NOW()
WHERE source = 'db-trigger' AND title LIKE 'BUG_BUG_LMS_%' AND active;

COMMIT;
