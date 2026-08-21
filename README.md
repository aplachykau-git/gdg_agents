# GDG Agentic Workspace (ADK)

This project is a multi-agent system built on the [Google Agent Development Kit (ADK) 2.0](https://adk.dev/), written in Python. It leverages the capabilities of Vertex AI (Gemini and Veo) models to automate events operations, document templates compilation, receipt scanning, scheduling conflicts analysis, and social media posting.

---

---

## 🏛️ System Architecture

```mermaid
%%{init: {
  'theme': 'dark',
  'themeVariables': {
    'darkMode': true,
    'background': '#0f172a',
    'primaryColor': '#1e293b',
    'primaryTextColor': '#f8fafc',
    'primaryBorderColor': '#475569',
    'lineColor': '#38bdf8',
    'textColor': '#f8fafc',
    'fontSize': '13px',
    'fontFamily': 'Inter, system-ui, -apple-system, sans-serif',
    'clusterBkg': '#131926',
    'clusterBorder': '#334155',
    'edgeLabelBackground': '#1e293b',
    'tertiaryColor': '#1e293b',
    'tertiaryBorderColor': '#334155'
  }
}}%%

flowchart TB
    subgraph CLIENT_LAYER["🖥️ 1. CLIENT & INTERACTION LAYER (A2UI)"]
        direction LR
        UI["<b>Svelte 5 Workspace Dashboard</b><br/><i>Port :5173 (Vite + Runes)</i><br/>• Floating Prompt Bar & Stager<br/>• Interactive Agenda Timeline<br/>• Multi-variant Post Deck<br/>• Multi-Agent DAG Topology"]
    end

    subgraph GATEWAY_LAYER["🌐 2. INGRESS & ADK ORCHESTRATION GATEWAY"]
        direction LR
        GW["<b>ADK Web Server / Reverse Proxy</b><br/><i>Port :8080 (FastAPI Engine)</i><br/>• SSE Streaming: <code>/run_sse</code><br/>• Apps & State Hub: <code>/list-apps</code>"]
        ROOT["<b>Root Orchestrator Agent</b><br/><i>gemini-2.5-flash</i><br/>• Intent Parsing & Decomposition<br/>• Sub-agent Routing & State Handoff"]
        GW <-->|Bidirectional SSE / REST| ROOT
    end

    subgraph AGENT_LAYER["🤖 3. SPECIALIZED WORKER AGENTS (Local & Remote A2A)"]
        direction TB
        
        subgraph LOCAL_AGENTS["⚡ Local Sub-Agents (In-Process Delegation)"]
            direction LR
            A_LINKEDIN["📱 <b>LinkedIn Post Generator</b><br/><i>gemini-2.5-flash</i><br/>• 3 Style Post Variants<br/>• Anti-Hallucination Guard"]
            A_REG["📋 <b>Registration Manager</b><br/><i>Data Partitioning Engine</i><br/>• CSV Parsing & Dedup<br/>• VIP & DOCX Exporter"]
            A_PLANNER["📅 <b>Event Planner</b><br/><i>gemini-2.5-flash</i><br/>• Tech Calendar Conflicts<br/>• Nager.Date Polish Holidays"]
            A_AGENDA["⏱️ <b>Agenda Formatter</b><br/><i>gemini-2.5-flash</i><br/>• Dynamic Slot Snapping<br/>• Interactive UI Timeline"]
            A_OFFICE["🔑 <b>Office Secretary</b><br/><i>gemini-2.5-flash</i><br/>• Key Access Management<br/>• Event Hub Reservations"]
        end

        subgraph REMOTE_A2A["🔗 Distributed A2A Microservices (Agent-to-Agent Protocol)"]
            direction LR
            A_VIDEO["🎬 <b>Live Video Editor A2A</b><br/><i>Port :8081 (Uvicorn / A2A App)</i><br/>• Face Landmark Verification<br/>• 9:16 Portrait Outpainting<br/>• Veo 3.1 / Omni Video Engine<br/>• HyperFrames GSAP 4K Render"]
            A_RECEIPT["🧾 <b>Receipt Scanner A2A</b><br/><i>Port :8082 (Uvicorn / A2A App)</i><br/>• gemini-2.5-pro OCR Engine<br/>• Pekao & NBP FX Rate Fetcher<br/>• Google Docs Report Exporter"]
        end
    end

    subgraph FOUNDATION_LAYER["☁️ 4. EXTERNAL AI FOUNDATION & ENTERPRISE SERVICES"]
        direction LR
        CLOUD_AI["<b>Google Vertex AI & GenAI</b><br/>• Gemini 2.5 Pro / Flash<br/>• Google Veo 3.1 & Omni Flash<br/>• Imagen Portrait Outpainting"]
        G_SUITE["<b>Google Workspace APIs</b><br/>• Google Drive API<br/>• Google Docs Engine"]
        FIN_APIS["<b>Public Financial & Calendar APIs</b><br/>• Pekao Bank FX Scraper<br/>• NBP Exchange Rate API<br/>• Nager.Date Holiday API"]
    end

    subgraph STORAGE_LAYER["💾 5. STORAGE, ARTIFACTS & STATE STORE"]
        direction LR
        S_STATE["<b>ADK Session Memory</b><br/>• InMemory / LocalStorage<br/>• Per-Agent Session State"]
        S_FILES["<b>Local Artifact File Store</b><br/>• <code>renders/</code> (4K MP4, GIF)<br/>• <code>assets/</code> (Staged Media)<br/>• <code>results/</code> (Generated DOCX)"]
    end

    %% Flows & Connections
    UI -->|1. User Prompt, Files & Commands| GW
    GW -->|2. Stream Real-time Events & Shimmer| UI
    
    ROOT -->|3a. Direct Transfer| LOCAL_AGENTS
    ROOT -->|3b. JSON-RPC Agent Card| REMOTE_A2A

    LOCAL_AGENTS -->|4a. Multimodal Prompt & Tools| CLOUD_AI
    LOCAL_AGENTS -->|4b. Public APIs| FIN_APIS
    LOCAL_AGENTS -->|4c. Save Documents| S_FILES

    REMOTE_A2A -->|5a. Veo / OCR Inference| CLOUD_AI
    REMOTE_A2A -->|5b. Auto-Export Expense Report| G_SUITE
    REMOTE_A2A -->|5c. Real-time FX Rates| FIN_APIS
    REMOTE_A2A -->|5d. Output 4K Video & Logs| S_FILES

    ROOT -.->|Read / Write State| S_STATE

    %% ByteByteGo Dark Mode Styling
    classDef clientStyle fill:#0c2340,stroke:#38bdf8,stroke-width:2px,color:#f0f9ff,rx:8px,ry:8px;
    classDef gwStyle fill:#451a03,stroke:#f59e0b,stroke-width:2px,color:#fef3c7,rx:8px,ry:8px;
    classDef localAgentStyle fill:#2e1065,stroke:#a855f7,stroke-width:2px,color:#faf5ff,rx:8px,ry:8px;
    classDef a2aStyle fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#ecfdf5,rx:8px,ry:8px;
    classDef cloudStyle fill:#4c0519,stroke:#f43f5e,stroke-width:2px,color:#fff1f2,rx:8px,ry:8px;
    classDef storageStyle fill:#1e293b,stroke:#64748b,stroke-width:2px,color:#f8fafc,rx:8px,ry:8px;

    class UI clientStyle;
    class GW,ROOT gwStyle;
    class A_LINKEDIN,A_REG,A_PLANNER,A_AGENDA,A_OFFICE localAgentStyle;
    class A_VIDEO,A_RECEIPT a2aStyle;
    class CLOUD_AI,G_SUITE,FIN_APIS cloudStyle;
    class S_STATE,S_FILES storageStyle;
```

---

## 🏗️ Project Structure

The workspace is organized into a clean, modular hierarchy:

```
gdg_krakow_tool/
├── agents/                       # All Google ADK Agents & sub-agents
│   ├── root_agent/               # Main coordinating Root Agent (gemini-2.5-flash)
│   ├── receipt_scanner/          # Receipt OCR & Google Docs expense report agent (gemini-2.5-pro)
│   ├── video_editor/             # Speaker card outpainting & Veo video generator (Veo + GSAP)
│   ├── linkedin_post_generator/  # LinkedIn announcement & recap post agent
│   ├── registration_manager/     # Registration sorting, capacity & organizers list agent
│   ├── event_planner/            # Tech calendar & holiday clash analyzer agent
│   ├── agenda_generator/         # Event timeline & speaker agenda formatting agent
│   └── office_secretary/         # Office key access & Event Hub reservation agent
│
├── frontend/                     # Custom Svelte 5 + Vite single-page dashboard
│   ├── src/
│   ├── public/
│   └── package.json
│
├── configs/                      # Configuration files (organizers list, API templates)
│   ├── organisers.txt
│   └── organisers.txt.example
│
├── docs/                         # Architecture, guides, and design specifications
│   ├── setup_guide.md
│   └── design.md
│
├── tests/                        # Evaluation datasets & test runners
│   ├── eval/
│   └── test_receipt_scanner.py
│
├── pyproject.toml                # Ruff & Python tools configuration
├── requirements.txt              # Python dependencies
├── setup.py                      # Python package setup
└── package.json                  # Root npm workspace scripts
```

---

## 🧠 ADK Architecture: Session State & Artifacts Management

The multi-agent system leverages core Google Agent Development Kit (ADK) 2.0 primitives:

1. **Model Tiering Strategy**:
   - **`gemini-2.5-pro`** is allocated to complex reasoning & dense document OCR (`receipt_scanner`).
   - **`gemini-2.5-flash`** is deployed across orchestrators and tool-calling agents for fast execution, high concurrency, and zero function-calling errors.
2. **Session State & Data Passing (`session.state`)**:
   - Rather than bloating prompt contexts with raw binary payloads or giant text tables across sub-agent transfers, agents communicate via workspace files and structured session state.
   - Staged media files (`assets/staged_media.mp4`, CSVs, generated posters) are managed per-agent and referenced through local storage paths.
3. **Progressive SSE Streaming**:
   - Real-time Server-Sent Events (`/run_sse`) stream function calls, function responses, and subagent state updates straight into the custom Svelte workspace.

---

---

## 🚀 Quick Start: Launch the Entire Workspace (A2A Architecture)

To spin up the complete distributed multi-agent system (Video Editor A2A on port 8081, Receipt Scanner A2A on port 8082, Root Orchestrator on port 8080, and the Svelte 5 frontend on port 5173), run **a single command**:

```bash
# Start all A2A microservices and frontend concurrently
./start_a2a_workspace.sh
# or
npm start
```

### 🌐 Running Services

* **Frontend UI Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Root Orchestrator Agent**: [http://localhost:8080](http://localhost:8080)
- **Video Editor A2A Service**: [http://localhost:8081/.well-known/agent-card.json](http://localhost:8081/.well-known/agent-card.json)
- **Receipt Scanner A2A Service**: [http://localhost:8082/.well-known/agent-card.json](http://localhost:8082/.well-known/agent-card.json)

---

### Individual Service Commands (Optional)

```bash
# 1. Video Editor A2A Server (Port 8081)
npm run a2a:video

# 2. Receipt Scanner A2A Server (Port 8082)
npm run a2a:receipt

# 3. Root Orchestrator Agent (Port 8080)
npm run a2a:root

# 4. Svelte Frontend (Port 5173)
npm run dev
```

*For detailed setup instructions, including Google Cloud authentication and template folder mapping, check out the [Setup Guide](file:///Users/aplachykau/Experiments/gdg_krakow_tool/docs/setup_guide.md).*

---

## 🎬 Video Editor Agent: Google Veo 3.1 & Gemini Omni Flash

The **Video Editor sub-agent** automates the creation of high-quality, cinematic marketing video intros for event speakers. It combines generative AI models for portrait outpainting and video animation with a deterministic, code-driven GSAP + HTML vector layout engine:

### 🌟 Key Capabilities & Latest Features

1. **Dual Video Generation Engines**:
   - **Google Veo 3.1 (`veo-3.1-fast-generate-001`)**: High-fidelity video generation via Vertex AI with curated cinematic lighting, subtle head motion, and realistic bokeh.
   - **Gemini Omni Flash (`gemini-omni-flash-preview`)**: Fast multimodal Image-to-Video generation via the Google AI Interactions API with unbroken single-shot camera dynamics.
   - Switchable dynamically via `VIDEO_ENGINE=veo` (default) or `VIDEO_ENGINE=omni` in `.env`.

2. **Speaker Portrait 9:16 Outpainting**:
   - Outpaints static photos into vertical 9:16 aspect ratio using Gemini/Imagen, preserving face identity while expanding background context for seamless vertical video framing.

3. **Dynamic Timeline & Adaptive Composition**:
   - **Dynamic Duration Detection**: Probes media with `ffprobe` to automatically adjust the composition timeline between 8s (Veo / Omni video loops) and 10s (custom video uploads).
   - **Adaptive Typewriter Timing**: Dynamically calculates typing speeds and easing curves based on the speaker title character count.
   - **Autoscaling Typography**: Font size dynamically scales to ensure multi-line talk titles fit within design boundaries.

4. **Multi-Format Concurrent Rendering**:
   - **4K Ultra HD MP4** (Upscaled high-bitrate video, `RENDER_4K=true`)
   - **1080p Full HD MP4** (Standard web video, `RENDER_ORDINARY=true`)
   - **Animated GIF** (Optimized for Slack / Discord / email embeds, `RENDER_GIF=true`)
   - **Avatar PNG Snapshots** (Extracted high-res frame for promotional badges)

### ⚙️ Video Generation & Render Configuration (`.env`)

| Variable | Values | Description |
| :--- | :--- | :--- |
| `VIDEO_ENGINE` | `veo` (default) \| `omni` | Selects the video generation model (`veo-3.1-fast-generate-001` or `gemini-omni-flash-preview`). |
| `ENABLE_VIDEO_GENERATION` | `true` \| `false` | Set to `false` for instant layout/text dry-runs using local placeholder assets without consuming video tokens. |
| `RENDER_4K` | `true` (default) \| `false` | Toggles rendering of the 4K Ultra HD MP4 video file. |
| `RENDER_ORDINARY` | `true` \| `false` (default) | Toggles rendering of the 1080p Full HD MP4 video file. |
| `RENDER_GIF` | `true` \| `false` (default) | Toggles automatic GIF conversion via FFmpeg. |

### Developer Commands (From Project Root or inside `agents/video_editor/`)

```bash
# Start local dev server with visual preview (scrub timeline at http://localhost:3000)
npm run video:dev

# Run linter, Chrome validation, and layout checks
npm run video:check

# Render video file
npm run video:render
```

---

## 🧹 Code Quality & Style Formatting (Python)

To keep the codebase clean, ordered, and formatted to a style guide (with a line length limit of **120 characters**), we use **Ruff** — an extremely fast Python linter and formatter configured via `pyproject.toml`.

Make sure your virtual environment is active, then run:

```bash
# Format Python code
ruff format .

# Check for lint errors and warnings
ruff check .

# Apply auto-fixes to check issues
ruff check --fix .
```
