# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Reading Room": a library management system with a student side and a librarian side.
FastAPI + SQLAlchemy + Alembic backend, React 19 + Vite 8 + Tailwind v4 frontend, PostgreSQL 16 with pgvector in Docker.
Deeper docs: `docs/ARCHITECTURE.md` (layers, rules, RAG), `docs/API.md` (every endpoint), `docs/BUG_FIXES.md` (LMS-BUG-NNN history; comments in code cite these IDs).

## Commands

All backend commands run from `backend/`. On Windows the venv binaries are in `.venv/Scripts/`; on macOS/Linux use `.venv/bin/`.

```bash
cp .env.example .env              # set LMS_JWT_SECRET; .env lives at the repo root, not in backend/
./backend/run.sh                  # DB container + venv + deps + alembic upgrade + seed + embeddings + uvicorn :8000
./backend/run.sh --test           # same setup, then pytest instead of the server
./backend/run.sh --no-reload      # uvicorn without --reload
./frontend/run.sh                 # pnpm install (via corepack) if needed, then vite dev on :5173
./frontend/run.sh --check         # oxlint + production build
./frontend/run.sh --build         # build + vite preview
```

Backend, directly:

```bash
.venv/Scripts/python -m pytest -q                                    # full suite, offline
.venv/Scripts/python -m pytest tests/test_api.py::test_category_full_crud -q   # one test
.venv/Scripts/alembic upgrade head                                    # apply migrations
.venv/Scripts/alembic revision --autogenerate -m "..."                # new migration
.venv/Scripts/python -m scripts.seed [--reset]                        # demo data; refuses if users exist, --reset wipes first
.venv/Scripts/python -m scripts.embed_books                           # embed catalog; skips unchanged books
.venv/Scripts/python -m scripts.smoke_api                             # live HTTP checks against a running server
.venv/Scripts/python -m scripts.test_rag_live                         # real embeddings + LLM; costs money
```

Frontend uses **pnpm** (pinned in package.json `packageManager`): `pnpm run dev`, `pnpm run build`, `pnpm run lint` (oxlint, config in `frontend/.oxlintrc.json`). There are no frontend tests.

## Environment

- Postgres runs as container `lms-postgres` on **localhost:5433** (not 5432). `db/init/` creates a second database `lms_test` on first boot of the volume.
- Settings come from `app/config.py` (pydantic-settings, `env_prefix="LMS_"`, reads the root `.env`, cached with `lru_cache`). The prefix is deliberate: an unprefixed machine-wide `DATABASE_URL` must not redirect the app (LMS-BUG-002).
- `LMS_AI_PROVIDER=none` (default) runs fully offline with keyword search and templated answers. `openrouter` enables embeddings plus an LLM, both through one `LMS_OPENROUTER_API_KEY`.
- Demo logins are in README.md; the seed builds students with specific trust profiles (reliable, needs approval, blocked, new).

## Tests

- `tests/conftest.py` forces `LMS_AI_PROVIDER=none` before importing the app, asserts the test URL contains `lms_test`, recreates the schema from `Base.metadata` once per session (Alembic is not used in tests), and `TRUNCATE ... RESTART IDENTITY CASCADE`s every table before each test. Tests never touch the dev database.
- The `client` fixture overrides `get_db`; services are also tested directly. Time-dependent rules take an injectable `now=` argument instead of mocking the clock.
- RAG tests (`tests/test_rag.py`) use a fake embedder and fake LLM, so they are deterministic and free.

## Architecture

Dependencies point one way: `routers/` → `services/` → `models.py`.

- **Routers** (`auth`, `catalog`, `loans`, `people`) handle HTTP only: Pydantic validation, role checks via `core/security.py` (`get_current_user`, `require_librarian`), then call a service. All are mounted under `/api` in `main.py`. `routers/_convert.py` builds response objects (e.g. `book_out`).
- **Services** own every business rule and never import FastAPI. They raise `services/errors.ServiceError(status, message)`, which `main.py` turns into `{"detail": ...}` JSON.
- **`schemas.py`** defines every request/response shape; response models are what decides what can leak (password hashes never appear).
- **Activity log**: every write calls `services/activity.log(db, actor_id, "entity.verb", entity, id, **details)` before commit. Keep doing this for new write endpoints.

Rules worth knowing before touching loans:
- **Trust score** (`trust_service`) is computed on demand, never stored: 100 − 10 per late return − 15 per unpaid fine − 25 if anything is overdue now + 2 per on-time return, clamped 0..100. ≥70 borrow instantly, 40–69 needs librarian approval, <40 blocked.
- **Concurrency** (`loan_service`): `borrow` locks the student row with `SELECT ... FOR UPDATE` to serialise one student's requests; loan approval locks the loan row; copies are taken with a single atomic `UPDATE ... WHERE available_copies > 0`, backed by a DB CHECK `0 <= available_copies <= total_copies`. A pending request already reserves its copy, so approval can't fail for lack of stock.
- Returning late creates the fine in the same transaction.
- **Sessions**: the JWT carries a session id; logout sets `sessions.logout_at`, and `get_current_session` rejects logged-out sessions, so logout really revokes the token. The browser gets the JWT in an httpOnly `lms_session` cookie (path `/api`, SameSite=Lax); `Authorization: Bearer` still works for API clients and tests. The frontend never stores the token.
- **Login rate limit** (`services/rate_limit.py`): in-memory, per process; 5 failures per IP+email and 20 per IP in 15 min, then 429 with `Retry-After`. Needs a shared store before running more than one worker.
- **Deploys**: no Docker, native Postgres; see `docs/DEPLOY.md`.

### AI / RAG

- `ai/provider.py` defines `Embedder` and `AIProvider` protocols with `None*` and `OpenRouter*` implementations, selected by `get_embedder()` / `get_provider()`. Network failures raise `AIError`; services catch it at that boundary and fall back to keyword search. Keep the fallback: the app must work with AI off.
- **Chunking**: one chunk per book. `embedding_service.book_text(book)` = title, author, category name, tags, description. `text_hash` = sha256 of model name + text, stored in `embedding_hash`, so only stale books get re-embedded.
- `embed_after_change(db, embedder, book_ids)` is called best-effort after book create/update and after a category **rename** (the category name is part of every book's embedded text). Anything that changes `book_text` inputs must call it.
- **Retrieval** (`assistant_service`): pgvector cosine distance (< 0.75) + Postgres full-text rank and tag overlap, fused with Reciprocal Rank Fusion (k=60); top 6 go to the LLM. No retrieved books means no LLM call.
- Embeddings are 2048-dim (`nvidia/nemotron-3-embed-1b`), above pgvector's 2000-dim index limit, so there is no vector index; an exact scan is fine at this catalog size. Changing `LMS_EMBEDDING_MODEL` requires re-running `scripts.embed_books`.
- `books.search` is a generated tsvector column (weighted title > author > description) with a GIN index; never write to it.
- The librarian AI brief (`insights_service.ai_brief`) must never send a student's name or email to the model.

### Frontend

- `src/api/client.js` is the only fetch wrapper: adds the JWT from `localStorage`, normalises errors, logs out on 401. Vite proxies `/api` to `127.0.0.1:8000`, so there is no CORS in dev.
- `src/context/AuthContext.jsx` holds the user; `App.jsx` renders a different route table per role (student vs librarian), and `components/Layout.jsx` holds the matching sidebar nav.
- Pages are grouped in two large files: `pages/student/StudentPages.jsx` and `pages/librarian/LibrarianPages.jsx`. Shared primitives (Button, PageHeader, Panel, Empty, Loading, ErrorNote, TrustBadge) live in `components/ui.jsx`.
- Design tokens are Tailwind v4 `@theme` variables in `src/index.css`; animations there respect `prefers-reduced-motion`. AI output is rendered as React text via `components/RichText.jsx`, never `innerHTML`.

## Conventions

- Schema changes go through a new Alembic revision in `backend/alembic/versions/`; never edit an applied one.
- `.env`, `backups/`, `test_results/` and `.playwright-mcp/` are git-ignored; keep the OpenRouter key out of commits and logs.
