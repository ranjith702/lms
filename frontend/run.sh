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

# pnpm is our standard. Use it if installed, otherwise run the exact version pinned in
# package.json ("packageManager") through corepack, which ships with Node.
if command -v pnpm >/dev/null; then PNPM=(pnpm)
elif command -v corepack >/dev/null; then PNPM=(corepack pnpm); export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
else fail "pnpm not found. Install it: npm install -g pnpm   (or enable corepack)"
fi

# Install only when the lockfile changed since the last install.
if [ ! -f node_modules/.modules.yaml ] || [ pnpm-lock.yaml -nt node_modules/.modules.yaml ]; then
  say "Installing dependencies (pnpm)"
  "${PNPM[@]}" install --frozen-lockfile --config.confirmModulesPurge=false
fi

# Warn (don't block) if the backend isn't up yet - Vite will start anyway.
if ! curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  echo "   note: backend not reachable on :8000 yet - run ../backend/run.sh in another terminal"
fi

case "${1:-}" in
  --check) say "Lint"; "${PNPM[@]}" run lint; say "Build"; "${PNPM[@]}" run build ;;
  --build) say "Build"; "${PNPM[@]}" run build; say "Serving build on http://localhost:4173"; exec "${PNPM[@]}" run preview ;;
  *)       say "Dev server on http://localhost:5173 - Ctrl+C to stop"; exec "${PNPM[@]}" run dev ;;
esac
