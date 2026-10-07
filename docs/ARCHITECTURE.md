# Architecture

## About the reference video

You asked me to follow the architecture steps from *"Modern Architecture 101 for New Engineers & Forgetful
Experts"* (Jerry Nixon, NDC Copenhagen 2025, https://youtu.be/WRg13Ze_UpY). I could read only the video's title,
not its transcript, so **this document does not claim to follow that talk's specific steps**.
What follows is a standard layered architecture with the reasoning for each choice.
If you write down the talk's main steps, each one can be mapped to a section here.

## The big picture

```
 Browser (React SPA, :5173)
   │  fetch('/api/...') + "Authorization: Bearer <JWT>"
   ▼
 Vite dev proxy  ──►  FastAPI (:8000)
                        │
                        ├─ routers/      HTTP only: validate input (Pydantic), check role, call a service
                        ├─ services/     business rules: trust score, borrow/return, fines, recommendations
                        ├─ ai/provider   pluggable "generate" step (NoneProvider today)
                        └─ models.py     SQLAlchemy tables
                               │
                               ▼
                       PostgreSQL 16 (Docker, localhost:5433, named volume = data survives restarts)
```

**One rule holds everything together: dependencies point one way.** Routers call services, services use models.
A service never knows it's being called over HTTP. It raises `ServiceError(409, "...")`, and `main.py` turns that
into a JSON response. So the same rules can later run from a CLI, a cron job or a chatbot without changes.

## Why each layer exists

| Layer | Owns | Does NOT do | Why it pays off here |
|---|---|---|---|
| **React pages** | What the user sees and clicks | Business rules | The UI can change without risk to the rules |
| **api/client.js** | JWT header, error messages, auto-logout on 401 | Page logic | One place to fix network behaviour |
| **Routers** | URL, input validation, role check | Rules, SQL details | Easy to read the API surface; Swagger is generated from it |
| **Services** | Every rule (trust, limits, fines, recommendations) | HTTP | Unit-tested directly with fake times (`now=...`) |
| **Models + Alembic** | Table shapes, constraints, migrations | Rules | Schema changes are versioned and repeatable |
| **PostgreSQL** | The truth, plus last-line checks (`available_copies >= 0`) | n/a | Even buggy code can't make copies negative |

## Data model

```
users ─┬─< sessions        one row per login; logout_at set on logout  -> login/logout history
       ├─< loans >── books >── categories
       ├─< fines (1 per late loan)
       └─< activity_log    append-only audit of every action
```

- `books.search` is a **generated** full-text column (title > author > description weights) with a GIN index.
  Postgres keeps it current; the app never updates it.
- CHECK constraints: roles, loan/fine statuses, `0 <= available_copies <= total_copies`.

## The rules, and where they live

| Rule | Code | How it's made safe |
|---|---|---|
| Trust score (computed, never stored) | `services/trust_service.py` | Can't go stale; reasons are returned so users see why |
| ≥70 instant · 40–69 approval · <40 blocked | `trust_service.level_for` | Thresholds in one place |
| Max 3 active loans, no duplicate book | `loan_service.borrow` | `SELECT … FOR UPDATE` on the student row serialises one student's requests (LMS-BUG-006) |
| Never issue more copies than exist | `loan_service._take_copy` | One atomic `UPDATE … WHERE available_copies > 0`, plus a DB CHECK |
| Fine = days late × `LMS_FINE_PER_DAY` | `loan_service.return_loan` | Created in the same transaction as the return |
| Pending request reserves the copy | `borrow` / `reject` | Approval can never fail for lack of copies |
| Logout really ends access | `core/security.get_current_session` | JWT carries a session id; a logged-out session is rejected |

## Recommendations and the assistant (where "AI" fits)

```
Question ──► RETRIEVE (Postgres full-text rank + tag overlap) ──► GENERATE (AIProvider) ──► answer + books
                         services/assistant_service.py              ai/provider.py
```

That's the shape of **RAG** (retrieval-augmented generation). Today *Generate* is `NoneProvider`, which writes
a templated sentence, so the app runs with no API keys. To switch on an LLM (e.g. an OpenRouter free model),
implement `generate(question, books)` in a new provider and set `LMS_AI_PROVIDER`. Nothing else changes.
Phase 2 swaps *Retrieve* for embeddings in pgvector.

Recommendations (`recommend_service.py`) are rule-based and explain themselves: same topic, similar themes or
author, co-borrowing ("readers like you"), something different, and popular picks for new readers. Each book
appears in only one section. The librarian's insights (`insights_service.py`) reuse the same pieces to suggest
actions and books for a particular student.

## Security choices

- Passwords: bcrypt. Tokens: HS256 JWT with a secret from `.env`; responses never include password hashes.
- Self-registration always creates a **student**; librarians come from the seed/admin only.
- Every librarian route uses `require_librarian` (tests check that students get 403 on 7 of them).
- All SQL goes through SQLAlchemy with bound parameters, including the search query (LMS-BUG-004).
- Postgres listens on 127.0.0.1 only, and compose refuses to start without a password (LMS-BUG-007).
- Settings are prefixed `LMS_` so another project's machine-wide `DATABASE_URL` can't redirect us (LMS-BUG-002).

## Known limits (honest list)

- Recommendations score books in Python: fine for hundreds of books; move into SQL or embeddings at ~10k.
- `localStorage` holds the JWT: simple and fine for a learning project; production would use an httpOnly cookie.
- No rate limiting on login yet.
