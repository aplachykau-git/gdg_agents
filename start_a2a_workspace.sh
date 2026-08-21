#!/usr/bin/env bash

# ==============================================================================
# 🚀 GDG Agentic Workspace - Complete A2A Multi-Service Launcher
# Launches Video Editor A2A (8081), Receipt Scanner A2A (8082),
# Root Orchestrator (8080), and Svelte 5 Frontend (5173).
# ==============================================================================

set -e

# Change to project root directory
cd "$(dirname "$0")"

echo "================================================================"
echo "🤖 Starting GDG Agentic Workspace (A2A Multi-Service Mode)..."
echo "================================================================"

# Check virtual environment
if [ -d ".venv" ]; then
    PYTHON_BIN=".venv/bin/python3"
    UVICORN_BIN=".venv/bin/uvicorn"
    ADK_BIN=".venv/bin/adk"
else
    PYTHON_BIN="python3"
    UVICORN_BIN="uvicorn"
    ADK_BIN="adk"
fi

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

# 1. Start Video Editor A2A Microservice (Port 8081)
echo "🎬 [1/4] Starting Video Editor A2A Service on http://127.0.0.1:8081..."
$UVICORN_BIN agents.video_editor.a2a_server:a2a_app --host 0.0.0.0 --port 8081 &
PIDS+=($!)

# 2. Start Receipt Scanner A2A Microservice (Port 8082)
echo "🧾 [2/4] Starting Receipt Scanner A2A Service on http://127.0.0.1:8082..."
$UVICORN_BIN agents.receipt_scanner.a2a_server:a2a_app --host 0.0.0.0 --port 8082 &
PIDS+=($!)

# Wait 2 seconds for A2A sub-agents to initialize
sleep 2

# 3. Start Root Orchestrator Agent (Port 8080)
echo "🧠 [3/4] Starting Root Orchestrator Agent on http://127.0.0.1:8080..."
VIDEO_AGENT_A2A_URL="http://localhost:8081" \
RECEIPT_AGENT_A2A_URL="http://localhost:8082" \
ADK_SUPPRESS_A2A_EXPERIMENTAL_FEATURE_WARNINGS="true" \
$ADK_BIN web --port 8080 agents &
PIDS+=($!)

# 4. Start Svelte Frontend (Port 5173)
echo "💻 [4/4] Starting Svelte Frontend on http://localhost:5173..."
npm run dev --prefix frontend &
PIDS+=($!)

echo ""
echo "================================================================"
echo "🎉 All services are up and running!"
echo "   ├─ 🌐 Frontend UI:        http://localhost:5173"
echo "   ├─ 🧠 Root Orchestrator:  http://localhost:8080"
echo "   ├─ 🎬 Video Editor A2A:   http://localhost:8081/.well-known/agent-card.json"
echo "   └─ 🧾 Receipt Scanner A2A: http://localhost:8082/.well-known/agent-card.json"
echo "================================================================"
echo "Press Ctrl+C to stop all services."
echo ""

# Wait for all background processes
wait
