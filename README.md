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
- **Ask the library:** describe what you want ("a book about space survival") and get matching books.

**Librarian**
- Desk: books out, waiting requests, overdue loans, unpaid fines, and students who need a look.
- Approve or reject requests (each one shows the student's trust score).
- Mark books returned (late returns create a fine automatically), mark fines paid or waived.
- A student profile that explains their record, suggests what to do next, and suggests books for them.
- Add, edit and delete books and categories. A full activity log.

**Everything is saved in PostgreSQL**: close the app, restart the database, log in again, and your loans,
fines, login/logout times and activity are still there (tested: see Verification below).

## Run it (Windows, Git Bash or PowerShell)

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
.venv/Scripts/python -m pytest -q              # 32 tests: rules, race conditions, API, permissions
.venv/Scripts/python -m scripts.smoke_api      # 35 live HTTP checks against the running server
cd ../frontend && npm run build && npm run lint
```

Last results (2026-10-07): pytest **32 passed**; smoke **35/35**; build clean; lint clean apart from React
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
      ai/provider.py       pluggable AI layer (none today, OpenRouter later)
    alembic/               versioned database migrations
    scripts/seed.py        demo data       scripts/smoke_api.py  live API check
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

- Turn on AI answers: add `app/ai/openrouter.py` and set `LMS_AI_PROVIDER=openrouter` (see `app/ai/provider.py`).
- Semantic search: pgvector + embeddings in place of keyword search (phase 2 of the assistant).
- Email/SMS due-date reminders; book reservations; book cover images.
