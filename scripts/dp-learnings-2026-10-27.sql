-- Completes the docs/BUG_FIXES.md import into DevPilot (mentor review 2026-10-27).
-- dp-learnings-2026-10-07.sql covers LMS-BUG-001,002,004..010 and LMS-BUG-011 (as LMS-RAG-LIVE-EVAL-FINDINGS).
-- This file adds LMS-BUG-003, tags the 011 row so it is found by its bug id, and records the measured
-- vector-index threshold. Idempotent: run it as often as you like.
INSERT INTO learnings (learning_id, category, title, content, summary, tags, applies_to, source,
                       project, scope, priority, always_load, active, source_file)
SELECT v.* FROM (VALUES
  ('LMS-BUG-003-REREAD-BEFORE-RUN', 'bug-pattern',
   'Placeholder code (if False, helper defined after use) left in search_books',
   $doc$No runtime error yet: the first draft of search_books contained an unused `if False` expression and a helper defined below its use. Found by reading the code back before running it. Fix: rewrote the function cleanly. Lesson: reread every file once before running the tests.$doc$,
   'Reread generated code once before running tests; it catches placeholders cheaply',
   ARRAY['library-m-system','lms-bug-003','code-review','python'], ARRAY['global'], 'claude-code-session',
   'library-m-system', 'global', 'low', false, true, 'backend/app/services/assistant_service.py'),
  ('LMS-VECTOR-INDEX-THRESHOLD-MEASURED', 'architecture',
   'Measured exact pgvector scan: 2048-dim, 64 books = ~2 ms; re-measure at 1,000 books',
   $doc$library-m-system embeds with nvidia/nemotron-3-embed-1b (2048 dims), above pgvector's 2000-dim index limit for the vector type, so retrieval is an exact scan. Measured 2026-10-27 with EXPLAIN ANALYZE (top-6 cosine, 64 embedded books, 920 kB table): 2.0-2.2 ms warm, 3.4 ms cold. A straight-line extrapolation (~0.03 ms/book) reaches a 50 ms budget near ~1,500 books, well below the earlier unmeasured "~10k" guess. Decision: re-measure at 1,000 books; switch to halfvec(2048) + HNSW (halfvec_cosine_ops) when the vector query exceeds 50 ms. HNSW is approximate, so compare recall against the exact scan before dropping it. Full record: docs/ARCHITECTURE.md "Decision record".$doc$,
   'Write index thresholds from a measurement, not a guess; here ~1.5k books, not 10k',
   ARRAY['library-m-system','pgvector','halfvec','hnsw','decision-record','performance'], ARRAY['global','postgres'],
   'claude-code-session', 'library-m-system', 'global', 'normal', false, true, 'docs/ARCHITECTURE.md')
) AS v(learning_id, category, title, content, summary, tags, applies_to, source, project, scope, priority,
       always_load, active, source_file)
WHERE NOT EXISTS (SELECT 1 FROM learnings l WHERE l.learning_id = v.learning_id);

UPDATE learnings SET tags = array_append(tags, 'lms-bug-011'), updated_at = NOW()
WHERE learning_id = 'LMS-RAG-LIVE-EVAL-FINDINGS' AND NOT ('lms-bug-011' = ANY(tags))
RETURNING learning_id;
