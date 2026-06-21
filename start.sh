#!/bin/bash
# ──────────────────────────────────────────────
# TuxTackleBox - Start Script
# ──────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 自动提升权限 ──
if [ "$EUID" -ne 0 ] && [ "$1" != "--no-sudo" ]; then
    if command -v sudo &>/dev/null && sudo -n true 2>/dev/null; then
        echo "→ 已有 passwordless sudo，以 root 重新执行..."
        exec sudo bash "$0" "$@"
    elif command -v sudo &>/dev/null; then
        echo "TuxTackleBox 需要 root 权限进行系统管理操作。"
        echo "PAM 认证需要读取 /etc/shadow（root 权限）。"
        exec sudo bash "$0" "$@"
    else
        echo "⚠ 未以 root 运行，且 sudo 不可用。"
        echo "  PAM 认证可能失败（无法读取 /etc/shadow）。"
        echo "  安装 sudo 或以 root 运行: su -c '$0'"
        echo ""
    fi
fi

# Read config
BACKEND_PORT=$(python3 -c "import json; print(json.load(open('config.json'))['backend']['port'])" 2>/dev/null || echo 5000)
FRONTEND_PORT=$(python3 -c "import json; print(json.load(open('config.json'))['frontend']['port'])" 2>/dev/null || echo 5173)
MODE="${1:-dev}"

mkdir -p logs

# ── Port check ──
check_port() {
    if ss -tlnp 2>/dev/null | grep -q ":$1 "; then
        echo "ERROR: Port $1 is already in use"
        exit 1
    fi
}

# ── Cleanup on exit ──
cleanup() {
    echo ""
    echo "Stopping..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    rm -f "$SCRIPT_DIR/.backend.pid" "$SCRIPT_DIR/.frontend.pid"
    echo "Stopped."
}
trap cleanup EXIT INT TERM

# ── Backend setup ──
setup_backend() {
    if [ ! -d "backend/venv" ]; then
        echo "Creating Python venv..."
        python3 -m venv --copies backend/venv || {
            echo "ERROR: Failed to create venv. Install python3-venv: sudo apt install python3-venv"
            exit 1
        }
    fi
    if [ ! -f "backend/venv/bin/python" ]; then
        echo "ERROR: venv appears broken. Remove it and retry: rm -rf backend/venv"
        exit 1
    fi
    source backend/venv/bin/activate
    echo "Installing Python dependencies..."
    pip install --upgrade pip -q 2>/dev/null
    pip install -r backend/requirements.txt -q
    deactivate 2>/dev/null || true
}

# ── Frontend setup ──
setup_frontend() {
    if [ ! -d "frontend/node_modules" ]; then
        echo "Installing frontend dependencies..."
        cd frontend
        if command -v pnpm &>/dev/null; then
            pnpm install
        else
            npm install
        fi
        cd "$SCRIPT_DIR"
    fi
}

# ── Start backend ──
start_backend() {
    check_port "$BACKEND_PORT"
    echo "Starting backend on :$BACKEND_PORT..."
    source backend/venv/bin/activate
    cd backend
    python3 main.py > "$SCRIPT_DIR/logs/backend.log" 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$SCRIPT_DIR/.backend.pid"
    cd "$SCRIPT_DIR"
    deactivate
    sleep 1
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "ERROR: Backend failed to start. Check logs/backend.log"
        exit 1
    fi
    echo "Backend started (PID: $BACKEND_PID)"
}

# ── Start frontend ──
start_frontend_dev() {
    check_port "$FRONTEND_PORT"
    echo "Starting frontend dev server on :$FRONTEND_PORT..."
    cd frontend
    if command -v pnpm &>/dev/null; then
        pnpm dev > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
    else
        npx vite --host > "$SCRIPT_DIR/logs/frontend.log" 2>&1 &
    fi
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > "$SCRIPT_DIR/.frontend.pid"
    cd "$SCRIPT_DIR"
    echo "Frontend started (PID: $FRONTEND_PID)"
}

build_frontend() {
    echo "Building frontend..."
    cd frontend
    if command -v pnpm &>/dev/null; then
        pnpm build
    else
        npm run build
    fi
    cd "$SCRIPT_DIR"
    echo "Frontend built to frontend/dist/"
}

# ── Main ──
echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║          TuxTackleBox v0.1.1-dev          ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

setup_backend

if [ "$MODE" = "--prod" ]; then
    # Production mode: build frontend, serve from backend
    setup_frontend
    build_frontend
    start_backend
    echo ""
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║  Access: http://127.0.0.1:$BACKEND_PORT          ║"
    echo "  ║  Mode:   Production                  ║"
    echo "  ║  Auth:   Linux PAM                   ║"
    echo "  ║  Press Ctrl+C to stop                ║"
    echo "  ╚═══════════════════════════════════════╝"
    echo ""
    wait
else
    # Dev mode: backend + frontend dev server
    setup_frontend
    start_backend
    start_frontend_dev
    echo ""
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║  Frontend: http://127.0.0.1:$FRONTEND_PORT      ║"
    echo "  ║  Backend:  http://127.0.0.1:$BACKEND_PORT       ║"
    echo "  ║  Mode:     Development                ║"
    echo "  ║  Auth:     Linux PAM                   ║"
    echo "  ║  Press Ctrl+C to stop                 ║"
    echo "  ╚═══════════════════════════════════════╝"
    echo ""
    wait
fi
