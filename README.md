# Reading Room: Library Management System

A small but reliable library app with a **student** side and a **librarian** side.
React frontend, FastAPI (Python) backend, PostgreSQL database in Docker.

| What | Where |
|---|---|
| How it's built (layers, data flow, why) | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Every API endpoint | [docs/API.md](docs/API.md) (live version: http://127.0.0.1:8000/docs) |
| Every bug hit while building and how it was fixed | [docs/BUG_FIXES.md](docs/BUG_FIXES.md) |
| Which Claude Code skills to use, and why | [docs/SKILLS-GUIDE.md](docs/SKILLS-GUIDE.md) |

## What it does

**Students**
- Browse 64 books in 8 categories. Click a cover to flip it and read the description.
- **One-click borrow.** If your trust score is 70 or more, you get the book instantly (a DUE stamp lands on the cover).
  From 40 to 69 the request goes to the librarian. Below 40, borrowing is blocked until you pay fines or return overdue books.
- My books (on loan, waiting for approval, reading history), fines, and a full login/logout and activity history.
- **For you:** recommendations by same topic, similar themes or author, "readers like you also borrowed", and "try something different".
- **Ask the library (RAG):** describe what you want ("a whodunit on a snowed-in train") and Claude answers using
  only books the library owns, found by meaning *and* by words.

**Librarian**
- Desk: books out, waiting requests, overdue loans, unpaid fines, and students who need a look.
- Approve or reject requests (each one shows the student's trust score).
- Mark books returned (late returns create a fine automatically), mark fines paid or waived.
- A student profile that explains their record, suggests what to do next, and suggests books for them,
  plus an **AI brief** written by Claude (the student's name and email are never sent to the AI).
- Add, edit and delete books and categories. A full activity log.

**Everything is saved in PostgreSQL**: close the app, restart the database, log in again, and your loans,
fines, login/logout times and activity are still there (tested: see Verification below).

## Run it: quick start

```bash
cp .env.example .env          # then set LMS_JWT_SECRET (and the AI keys below if you want RAG)
./backend/run.sh              # terminal 1: DB + deps + migrations + seed + embeddings + API on :8000
./frontend/run.sh             # terminal 2: React app on http://localhost:5173
```

`backend/run.sh --test` runs pytest; `frontend/run.sh --check` runs lint + build. Both scripts are safe to re-run.

## Run it step by step (Windows, Git Bash or PowerShell)

Needs: Docker Desktop, Python 3.11+, Node 20+.

```bash
# 1. Settings: copy the example and set your own secret
cp .env.example .env
#    edit .env -> LMS_JWT_SECRET (generate: python -c "import secrets; print(secrets.token_hex(32))")

# 2. Database (PostgreSQL 16 on localhost:5433; data kept in a Docker volume)
docker compose up -d

# 3. Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt     # macOS/Linux: .venv/bin/python
.venv/Scripts/alembic upgrade head                           # create tables
.venv/Scripts/python -m scripts.seed                         # demo data (add --reset to wipe and reseed)
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173
```

### Turn on the AI (optional)

Without this the app works fully, using keyword search and templated answers.

```bash
# in .env
LMS_AI_PROVIDER=openrouter
LMS_OPENROUTER_API_KEY=sk-or-...           # your key from https://openrouter.ai/keys (never commit it)
LMS_OPENROUTER_MODEL=anthropic/claude-haiku-4.5
LMS_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free

# then, from backend/
.venv/Scripts/python -m scripts.embed_books      # embeds the catalog (re-run any time; skips unchanged books)
.venv/Scripts/python -m scripts.test_rag_live    # live check of RAG + suggestions (a few cents of Claude usage)
# restart uvicorn so it reads the new .env
```

Database note: the Postgres image is `pgvector/pgvector:pg16` (Postgres 16 + the vector extension).

### Demo logins

| Email | Password | Story |
|---|---|---|
| librarian@library.dev | Librarian@123 | Librarian |
| asha@library.dev | Student@123 | Reliable reader: borrows instantly |
| ravi@library.dev | Student@123 | Late returns + unpaid fines: needs approval |
| meera@library.dev | Student@123 | Overdue book + fines: blocked |
| kiran@library.dev | Student@123 | Brand new student |

The login page has buttons that fill these in.

## Verification

```bash
cd backend
.venv/Scripts/python -m pytest -q              # 45 tests, offline (fake AI): rules, races, API, permissions, RAG
.venv/Scripts/python -m scripts.smoke_api      # 35 live HTTP checks against the running server
cd ../frontend && npm run build && npm run lint
```

Last results (2026-10-07): pytest **44 passed**; smoke **35/35**; live RAG test **10/10**
(Nemotron embeddings + Claude Haiku 4.5, report in `test_results/rag/`); build clean; lint clean apart from React
fast-refresh hints. Browser walkthrough screenshots are saved locally in `test_results/ui/` (not committed).
After `docker compose restart db`, row counts were identical (15 sessions, 16 loans, 50 activity rows)
and the smoke test still passed.

## Project layout

```
library-m-system/
  docker-compose.yml       Postgres 16 (localhost only, password required from .env)
  .env.example             all settings, prefixed LMS_
  db/init/                 creates the lms_test database on first start
  backend/
    app/
      main.py              FastAPI app, CORS, error handler, /api/health
      config.py db.py      settings + database session
      models.py            7 tables (users, categories, books, loans, fines, sessions, activity_log)
      schemas.py           request/response shapes (passwords never leave the server)
      core/security.py     bcrypt, JWT, session check, role guards
      routers/             HTTP only: auth, catalog, loans (+fines), people (insights, recs, assistant, activity)
      services/            business rules: trust, loans, fines, recommendations, insights, assistant
      ai/provider.py       pluggable AI layer: Embedder + AIProvider (none | openrouter)
    alembic/               versioned database migrations
    scripts/seed.py        demo data       scripts/smoke_api.py  live API check
    scripts/embed_books.py compute embeddings   scripts/test_rag_live.py  live RAG evaluation
    tests/                 pytest (runs against lms_test, never your real data)
  frontend/
    src/api/client.js      one fetch wrapper: JWT, errors, auto-logout on 401
    src/context/           AuthContext (login state survives a reload)
    src/components/        BookCard (flip + stamp), Layout (role-aware sidebar), ui kit
    src/pages/student/     Catalog, MyBooks, ForYou + Assistant, MyFines, History
    src/pages/librarian/   Desk, Requests, Loans, Fines, Students, StudentProfile, Books, Assistant, Activity
  docs/                    ARCHITECTURE, API, BUG_FIXES, SKILLS-GUIDE
  scripts/                 DevPilot learnings SQL for the bugs above
```

## Next steps (not built yet)

- Cache question embeddings, and add rate limiting on `/assistant/ask` and `/ai-brief` (each call costs money).
- Switch embeddings to `halfvec` + an HNSW index once the catalog grows past ~10k books.
- Email/SMS due-date reminders; book reservations; book cover images.
