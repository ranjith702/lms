#!/usr/bin/env bash
# Start the Reading Room backend: database -> deps -> migrations -> demo data -> embeddings -> API.
#
#   ./run.sh              start everything on http://127.0.0.1:8000  (Swagger: /docs)
#   ./run.sh --test       run the pytest suite instead of starting the server
#   ./run.sh --no-reload  start without auto-reload (closer to how it runs in production)
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

# ---- 1. database (Postgres 16 + pgvector in Docker) ---------------------------
command -v docker >/dev/null || fail "Docker is not installed"
docker info >/dev/null 2>&1 || fail "Docker is not running. Start Docker Desktop and re-run."
say "Starting PostgreSQL (docker compose)"
(cd "$ROOT_DIR" && docker compose up -d db >/dev/null)
say "Waiting for the database to be healthy"
for _ in $(seq 1 30); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' lms-postgres 2>/dev/null)" = "healthy" ] && break
  sleep 2
done
[ "$(docker inspect -f '{{.State.Health.Status}}' lms-postgres)" = "healthy" ] || fail "Database did not become healthy"

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
