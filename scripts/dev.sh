#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

: "${BACKEND_PORT:=1689}"
: "${FRONTEND_PORT:=1688}"

if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "請先在 backend 建立並安裝 venv：cd backend && python3 -m venv .venv ... "
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "請先在 frontend 安裝相依套件：cd frontend && npm install"
  exit 1
fi

run_backend() {
  (
    cd "$BACKEND_DIR" && source .venv/bin/activate && \
      uvicorn app.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT"
  ) &
}

run_frontend() {
  (
    cd "$FRONTEND_DIR" && \
      npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
  ) &
}

cleanup() {
  echo
  echo "停止服務中..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

run_backend
BACKEND_PID=$!
run_frontend
FRONTEND_PID=$!

echo "後端: http://localhost:$BACKEND_PORT"
echo "前端: http://localhost:$FRONTEND_PORT"
echo "停止請按 Ctrl+C"

wait
