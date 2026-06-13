#!/usr/bin/env bash
# 一鍵啟動前後端開發伺服器。
# 預設埠：後端 1689、前端 1688，可用環境變數 BACKEND_PORT / FRONTEND_PORT 覆寫。
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PORT="${BACKEND_PORT:-1689}"
FRONTEND_PORT="${FRONTEND_PORT:-1688}"

# ── Node：Vite 5 需要 Node 18+，若當前版本過舊則用 nvm 自動切換 ──────────────
ensure_node() {
  local major
  major="$(node -v 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/')"
  if [ -n "$major" ] && [ "$major" -ge 18 ]; then
    return 0
  fi
  echo "目前 Node 版本過舊（$(node -v 2>/dev/null || echo 無)），嘗試用 nvm 切換到 18+ ..."
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  # shellcheck disable=SC1091
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
  if command -v nvm >/dev/null 2>&1; then
    nvm use 22 >/dev/null 2>&1 || nvm use 20 >/dev/null 2>&1 || nvm use 18 >/dev/null 2>&1 || true
  fi
  major="$(node -v 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/')"
  if [ -z "$major" ] || [ "$major" -lt 18 ]; then
    echo "✗ 找不到 Node 18+，請先安裝（例如 nvm install 22）。前端將無法啟動。"
    exit 1
  fi
  echo "✓ 已切換到 Node $(node -v)"
}

# ── 相依環境：缺了就自動建立，而非直接退出 ──────────────────────────────────
ensure_backend_deps() {
  if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "backend/.venv 不存在，建立並安裝相依 ..."
    python3 -m venv "$BACKEND_DIR/.venv"
    "$BACKEND_DIR/.venv/bin/pip" install -q --upgrade pip
    "$BACKEND_DIR/.venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
  fi
}

ensure_frontend_deps() {
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "frontend/node_modules 不存在，執行 npm install ..."
    ( cd "$FRONTEND_DIR" && npm install )
  fi
}

# ── 啟動前釋放埠號，避免殘留進程占用導致跳埠或起不來 ────────────────────────
free_port() {
  local port="$1"
  local pids
  pids="$(lsof -t -i ":$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "釋放埠 $port（kill -9 $pids）"
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

# ── 啟動後健康檢查：確認兩邊真的活著 ────────────────────────────────────────
health_check() {
  local ok_backend="" ok_frontend="" i
  for i in $(seq 1 20); do
    if [ -z "$ok_backend" ] && curl -sf "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
      ok_backend=1
    fi
    if [ -z "$ok_frontend" ] && curl -sf "http://127.0.0.1:$FRONTEND_PORT/" >/dev/null 2>&1; then
      ok_frontend=1
    fi
    [ -n "$ok_backend" ] && [ -n "$ok_frontend" ] && break
    sleep 1
  done
  echo "------------------------------------------"
  echo "後端 http://localhost:$BACKEND_PORT   $([ -n "$ok_backend" ] && echo '✓ 正常' || echo '✗ 未回應')"
  echo "前端 http://localhost:$FRONTEND_PORT   $([ -n "$ok_frontend" ] && echo '✓ 正常' || echo '✗ 未回應')"
  echo "------------------------------------------"
}

cleanup() {
  echo
  echo "停止服務中..."
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ensure_node
ensure_backend_deps
ensure_frontend_deps
free_port "$FRONTEND_PORT"
free_port "$BACKEND_PORT"

( cd "$BACKEND_DIR" && source .venv/bin/activate \
    && exec uvicorn app.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" ) &
BACKEND_PID=$!

( cd "$FRONTEND_DIR" \
    && exec npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" ) &
FRONTEND_PID=$!

health_check
echo "停止請按 Ctrl+C"
wait
