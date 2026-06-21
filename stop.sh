#!/bin/bash
# ──────────────────────────────────────────────
# PenguinFu - Stop Script
# ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Stopping PenguinFu..."

if [ -f "$SCRIPT_DIR/.backend.pid" ]; then
    PID=$(cat "$SCRIPT_DIR/.backend.pid")
    kill "$PID" 2>/dev/null && echo "Backend stopped (PID: $PID)" || echo "Backend already stopped"
    rm -f "$SCRIPT_DIR/.backend.pid"
fi

if [ -f "$SCRIPT_DIR/.frontend.pid" ]; then
    PID=$(cat "$SCRIPT_DIR/.frontend.pid")
    kill "$PID" 2>/dev/null && echo "Frontend stopped (PID: $PID)" || echo "Frontend already stopped"
    rm -f "$SCRIPT_DIR/.frontend.pid"
fi

# Kill any remaining processes on our ports
BACKEND_PORT=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/config.json'))['backend']['port'])" 2>/dev/null || echo 5000)
FRONTEND_PORT=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/config.json'))['frontend']['port'])" 2>/dev/null || echo 5173)

fuser -k "$BACKEND_PORT/tcp" 2>/dev/null
fuser -k "$FRONTEND_PORT/tcp" 2>/dev/null

echo "Done."
