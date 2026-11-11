#!/usr/bin/env bash

# ==============================================================================
# 🚀 Community Studio - Complete A2A Multi-Service Launcher
# Launches Video Editor A2A (8181), Receipt Scanner A2A (8182),
# Root Orchestrator (8180), and Svelte 5 Frontend (5180).
# ==============================================================================

set -e

# Change to project root directory
cd "$(dirname "$0")"

echo "================================================================"
echo "🤖 Starting Community AI Studio (A2A Multi-Service Mode)..."
echo "================================================================"

command -v uv >/dev/null 2>&1 || {
    echo "uv is required. Install uv and run: uv sync --locked"
    exit 1
}

uv sync --locked

# Track child background PIDs
PIDS=()

cleanup() {
    echo ""
    echo "🛑 Shutting down all A2A agent services and frontend..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
    echo "✅ All services stopped cleanly."
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM EXIT

# 1. Start Video Editor A2A Microservice (Port 8181)
echo "🎬 [1/4] Starting Video Editor A2A Service on http://127.0.0.1:8181..."
uv run --locked --no-sync uvicorn agents.video_editor.a2a_server:a2a_app --host 0.0.0.0 --port 8181 &
PIDS+=($!)

# 2. Start Receipt Scanner A2A Microservice (Port 8182)
echo "🧾 [2/4] Starting Receipt Scanner A2A Service on http://127.0.0.1:8182..."
uv run --locked --no-sync uvicorn agents.receipt_scanner.a2a_server:a2a_app --host 0.0.0.0 --port 8182 &
PIDS+=($!)

# Wait 2 seconds for A2A sub-agents to initialize
sleep 2

# 3. Start Root Orchestrator Agent (Port 8180)
echo "🧠 [3/4] Starting Root Orchestrator Agent on http://127.0.0.1:8180..."
VIDEO_AGENT_A2A_URL="http://localhost:8181" \
RECEIPT_AGENT_A2A_URL="http://localhost:8182" \
ADK_SUPPRESS_A2A_EXPERIMENTAL_FEATURE_WARNINGS="true" \
uv run --locked --no-sync adk web --port 8180 agents &
PIDS+=($!)

# 4. Start Svelte Frontend (Port 5180)
echo "💻 [4/4] Starting Svelte Frontend on http://localhost:5180..."
npm run dev --prefix frontend &
PIDS+=($!)

echo ""
echo "================================================================"
echo "🎉 All services are up and running!"
echo "   ├─ 🌐 Frontend UI:        http://localhost:5180"
echo "   ├─ 🧠 Root Orchestrator:  http://localhost:8180"
echo "   ├─ 🎬 Video Editor A2A:   http://localhost:8181/.well-known/agent-card.json"
echo "   └─ 🧾 Receipt Scanner A2A: http://localhost:8182/.well-known/agent-card.json"
echo "================================================================"
echo "Press Ctrl+C to stop all services."
echo ""

# Wait for all background processes
wait
