#!/usr/bin/env bash
# Start the Reading Room backend: database -> deps -> migrations -> demo data -> embeddings -> API.
#
#   ./run.sh              start everything on http://127.0.0.1:8000  (Swagger: /docs)
#   ./run.sh --test       run the pytest suite instead of starting the server
#   ./run.sh --no-reload  start without auto-reload (closer to how it runs in production)
#   LMS_NO_DOCKER=1 ./run.sh   never touch Docker; require a native PostgreSQL
#
# Works in Git Bash on Windows and in bash on macOS/Linux. Safe to re-run: every step is idempotent.
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$BACKEND_DIR/.." && pwd)"
PORT="${LMS_PORT:-8000}"

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# ---- 0. settings -------------------------------------------------------------
[ -f "$ROOT_DIR/.env" ] || fail "No .env in $ROOT_DIR. Run: cp .env.example .env  (then set LMS_JWT_SECRET)"
grep -q '^LMS_JWT_SECRET=change-me' "$ROOT_DIR/.env" && fail "Set a real LMS_JWT_SECRET in .env first"

# ---- 1. database (PostgreSQL 16 + pgvector) ------------------------------------
# Deployed environments run a native PostgreSQL service - no Docker (team standard).
# Locally: if a database already answers on the host:port in LMS_DATABASE_URL we use it;
# only when nothing is listening do we fall back to the Docker dev container.
DB_URL="$(grep -E '^LMS_DATABASE_URL=' "$ROOT_DIR/.env" | head -1 | cut -d= -f2-)"
[ -n "$DB_URL" ] || fail "LMS_DATABASE_URL is missing from .env"
DB_HOSTPORT="$(printf '%s' "$DB_URL" | sed -E 's#^[^@]*@([^/?]*).*#\1#')"
DB_HOST="${DB_HOSTPORT%%:*}"; DB_PORT="${DB_HOSTPORT##*:}"
[ "$DB_PORT" = "$DB_HOSTPORT" ] && DB_PORT=5432
db_listening() { (exec 3<>"/dev/tcp/$DB_HOST/$DB_PORT") 2>/dev/null; }

if db_listening; then
  say "Using the PostgreSQL already running on $DB_HOST:$DB_PORT"
elif [ "${LMS_NO_DOCKER:-0}" = 1 ] || ! command -v docker >/dev/null; then
  fail "No database on $DB_HOST:$DB_PORT. Start your native PostgreSQL 16 + pgvector (docs/DEPLOY.md)."
else
  docker info >/dev/null 2>&1 || fail "No database on $DB_HOST:$DB_PORT and Docker isn't running. Start one of them."
  say "Starting the local dev PostgreSQL (docker compose - dev only, never for deploys)"
  (cd "$ROOT_DIR" && docker compose up -d db >/dev/null)
  say "Waiting for the database to be healthy"
  for _ in $(seq 1 30); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' lms-postgres 2>/dev/null)" = "healthy" ] && break
    sleep 2
  done
  [ "$(docker inspect -f '{{.State.Health.Status}}' lms-postgres)" = "healthy" ] || fail "Database did not become healthy"
fi

# ---- 2. python virtualenv + dependencies -------------------------------------
cd "$BACKEND_DIR"
if [ -x .venv/Scripts/python ]; then PY=.venv/Scripts/python      # Windows
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python             # macOS / Linux
else
  say "Creating virtualenv"
  SYS_PY="$(command -v python3 || command -v python)" || fail "Python 3.11+ is not installed"
  "$SYS_PY" -m venv .venv
  if [ -x .venv/Scripts/python ]; then PY=.venv/Scripts/python; else PY=.venv/bin/python; fi
fi
# Reinstall only when requirements.txt changed since the last successful install.
if [ ! -f .venv/.req-stamp ] || [ requirements.txt -nt .venv/.req-stamp ]; then
  say "Installing Python dependencies"
  "$PY" -m pip install -q -r requirements.txt
  touch .venv/.req-stamp
fi

if [ "${1:-}" = "--test" ]; then
  say "Running pytest (uses the lms_test database, never your real data)"
  exec "$PY" -m pytest -q
fi

# ---- 3. schema + demo data ----------------------------------------------------
say "Applying migrations (alembic upgrade head)"
"$PY" -m alembic upgrade head
say "Seeding demo data (skipped if users already exist)"
"$PY" -m scripts.seed || true

# ---- 4. embeddings for RAG (only when an AI provider is configured) -----------
if grep -q '^LMS_AI_PROVIDER=openrouter' "$ROOT_DIR/.env"; then
  say "Embedding books (only new or changed books are sent to the API)"
  "$PY" -m scripts.embed_books || echo "   (embedding failed - the assistant falls back to keyword search)"
fi

# ---- 5. API -------------------------------------------------------------------
RELOAD="--reload"; [ "${1:-}" = "--no-reload" ] && RELOAD=""
say "API on http://127.0.0.1:$PORT  (docs: http://127.0.0.1:$PORT/docs)  - Ctrl+C to stop"
exec "$PY" -m uvicorn app.main:app $RELOAD --host 127.0.0.1 --port "$PORT"
