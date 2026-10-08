#!/usr/bin/env bash
# Start the Reading Room frontend (Vite dev server on http://localhost:5173).
# Calls to /api are proxied to the backend on 127.0.0.1:8000, so start ../backend/run.sh first.
#
#   ./run.sh          dev server with hot reload
#   ./run.sh --check  lint + production build only (no server)
#   ./run.sh --build  production build, then serve it with `vite preview`
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

command -v node >/dev/null || fail "Node 20+ is not installed"
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[ "$NODE_MAJOR" -ge 20 ] || fail "Node 20+ required (found $(node -v))"

# Install only when the lockfile changed since the last install.
if [ ! -d node_modules ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
  say "Installing npm dependencies"
  npm ci
fi

# Warn (don't block) if the backend isn't up yet - Vite will start anyway.
if ! curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  echo "   note: backend not reachable on :8000 yet - run ../backend/run.sh in another terminal"
fi

case "${1:-}" in
  --check) say "Lint"; npm run lint; say "Build"; npm run build ;;
  --build) say "Build"; npm run build; say "Serving build on http://localhost:4173"; exec npm run preview ;;
  *)       say "Dev server on http://localhost:5173 - Ctrl+C to stop"; exec npm run dev ;;
esac
