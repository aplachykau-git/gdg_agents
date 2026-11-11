# Community AI Studio

This project is a multi-agent system built on the [Google Agent Development Kit (ADK) 2.14](https://adk.dev/), written in Python 3.12. It leverages the capabilities of Google AI and Vertex AI (Gemini models) to automate events operations, document templates compilation, receipt scanning, scheduling conflicts analysis, QR code generation, and social media planning.

---

## 🏛️ System Architecture

The diagram source is [`docs/architecture.mmd`](docs/architecture.mmd); `make diagrams` renders it to [`docs/assets/`](docs/assets/architecture_diagram.png) (SVG, PNG, PDF). Edit the `.mmd` file, then re-render and paste it here.

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
    subgraph CLIENT_LAYER["1. CLIENT: Svelte 5 studio (local Vite :5173 or Firebase Hosting)"]
        direction LR
        UI["<b>Chat workspace</b><br/>• Agent catalog, chat, live tool status<br/>• Settings: chapter name, video render, Google Drive<br/>• Browser storage: settings + saved event profile"]
        CARDS["<b>Result cards (A2UI)</b><br/>rendered from the backend <code>ui</code> payload<br/>on the shared ResultCard shell<br/>• Video + scenario deck • Countdown post plan<br/>• Event details • Recognised receipts • QR code<br/>• Agenda • E-mail draft • Dates • Documents"]
        PICKER["<b>Google Drive Picker</b><br/>pick folder / template / files<br/>Docs, Sheets, PDFs, images as attachments"]
    end

    subgraph GATEWAY_LAYER["2. ENTRY POINTS"]
        direction LR
        GW["<b>ADK API server</b><br/><i>local :8080 or Cloud Run community-root-agent</i><br/>• SSE streaming <code>/run_sse</code>, <code>/list-apps</code><br/>• Session state: settings + event_* keys on every message"]
        ROOT["<b>Main (root_agent)</b><br/><i>gemini-3.8-flash</i><br/>• Intent routing to 8 specialists<br/>• OIDC client for private A2A"]
        MCP["<b>MCP server (experiment)</b><br/><i>agents/mcp_server.py</i><br/>video scenarios + render, registrations,<br/>receipts, QR codes for Claude / Gemini CLI / IDEs"]
        GW <-->|SSE / REST| ROOT
    end

    subgraph AGENT_LAYER["3. SPECIALIST AGENTS"]
        direction TB
        subgraph LOCAL_AGENTS["In-process sub-agents"]
            direction LR
            A_SOCIAL["<b>Social Planner</b><br/><i>linkedin_post_generator</i><br/>• Speaker announcements, recaps<br/>• Countdown plan: LinkedIn, Instagram,<br/>Facebook, X, Threads, Bluesky, Mastodon<br/>• Event profile card (date, site, socials)"]
            A_QR["<b>QR Code Generator</b><br/><i>qr_code_generator</i><br/>• Rounded QR codes<br/>• Flat SVG + PNG"]
            A_REG["<b>Registrations Manager</b><br/><i>registration_manager</i><br/>• Roster clean and dedup<br/>• PII guard, DOCX roster"]
            A_PLANNER["<b>Event Scheduler</b><br/><i>event_planner</i><br/>• Polish holidays<br/>• Meetup conflicts"]
            A_AGENDA["<b>Agenda Formatter</b><br/><i>agenda_generator</i><br/>• Minute-level timeline"]
            A_OFFICE["<b>Office Secretary</b><br/><i>office_secretary</i><br/>• Key access and room e-mails"]
        end
        subgraph REMOTE_A2A["Private A2A services (local :8081 / :8082, Cloud Run with IAM OIDC)"]
            direction LR
            A_VIDEO["<b>Live Video Editor</b><br/><i>video_editor</i><br/>• Face check, 9:16 outpainting<br/>• Scenario deck, Gemini Omni Flash video<br/>• HyperFrames render with cover frame<br/>• MP4 1080p / 4K, GIF, poster"]
            A_RECEIPT["<b>Receipt Scanner</b><br/><i>receipt_scanner</i><br/>• Multimodal OCR, multi-page PDF stitching<br/>• Community FX, manual rate fallback<br/>• Grouped rows & synced 2-per-row proofs<br/>• Recognised-receipts card + CSV, Google Docs"]
        end
        CORE["<b>Shared core: agents/common</b><br/>ui_payloads.py (card contract, mirrored in frontend/src/lib/ui/payloads.js)<br/>event_profile.py (event + social profiles) • runtime.py (SQLite sessions locally, optional Postgres)"]
    end

    subgraph INFRA_LAYER["4. STORAGE, AI AND EXTERNAL SERVICES"]
        direction LR
        FILES["<b>Media and files</b><br/>local renders/ and results/ (dev default)<br/>or Cloud Storage (30-day lifecycle)"]
        AI_BACKEND["<b>Gemini API / Vertex AI</b><br/>Gemini 3.8 Flash<br/>Gemini Omni Flash<br/>Flash Lite Image"]
        WORKSPACE["<b>Google Workspace</b><br/>Docs, Drive, Sheets"]
        EXTERNAL["<b>External APIs</b><br/>NBP / Pekao / Frankfurter / Open ER FX,<br/>Nager.Date holidays, Google Search"]
    end

    UI --- CARDS
    UI --- PICKER
    UI -->|HTTPS / SSE| GW
    ROOT -->|in-process transfer| A_SOCIAL
    ROOT --> A_QR
    ROOT --> A_REG
    ROOT --> A_PLANNER
    ROOT --> A_AGENDA
    ROOT --> A_OFFICE
    ROOT -->|A2A + OIDC| A_VIDEO
    ROOT -->|A2A + OIDC| A_RECEIPT
    MCP -.->|same tool cores| A_VIDEO
    MCP -.-> A_QR
    A_SOCIAL -->|inference| AI_BACKEND
    A_VIDEO -->|video generation| AI_BACKEND
    A_RECEIPT -->|OCR| AI_BACKEND
    A_VIDEO <-->|renders| FILES
    A_QR -->|SVG / PNG| FILES
    A_RECEIPT -->|reports| WORKSPACE
    A_RECEIPT -->|FX rates| EXTERNAL
    A_PLANNER -->|holidays, events| EXTERNAL
    PICKER -->|drive.file, exported in the browser| WORKSPACE
```

---

## 🏗️ Project Structure

The workspace is organized into a clean, modular hierarchy:

```
community_studio/
├── agents/                       # All Google ADK Agents & sub-agents
│   ├── root_agent/               # Main coordinating Root Agent (gemini-3.8-flash)
│   ├── receipt_scanner/          # Receipt OCR & Google Docs expense report agent (gemini-3.8-flash)
│   ├── video_editor/             # Speaker outpainting & video generator (gemini-3.8-flash, Gemini Omni, GSAP)
│   ├── linkedin_post_generator/  # Social Planner: announcements, recaps, countdown plans, event profile (gemini-3.8-flash)
│   ├── registration_manager/     # Registration sorting, capacity & privacy agent (gemini-3.8-flash)
│   ├── event_planner/            # Tech calendar & holiday clash analyzer agent (gemini-3.8-flash)
│   ├── agenda_generator/         # Event timeline & speaker agenda formatting agent (gemini-3.8-flash)
│   ├── office_secretary/         # Office key access & Event Hub reservation agent (gemini-3.8-flash)
│   ├── qr_code_generator/        # Rounded QR codes for links: flat SVG + PNG (gemini-3.8-flash)
│   ├── common/                   # Shared core: ui_payloads (cards), event_profile, runtime (sessions), A2A auth
│   └── mcp_server.py             # MCP server exposing the heavy tools (experiment)
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
│   ├── architecture.mmd          # Architecture diagram source (make diagrams -> docs/assets/)
│   ├── SOLUTION_ARCHITECTURE.md
│   ├── setup_guide.md
│   └── design.md
│
├── tests/                        # Python unittest suite (no network, scripted model)
│
├── pyproject.toml                # Python package and tool configuration
├── uv.lock                       # Locked Python dependencies
└── package.json                  # Root npm workspace scripts
```

---

## 🧠 ADK Architecture: Session State & Artifacts Management

The multi-agent system leverages core Google Agent Development Kit (ADK) 2.14 primitives:

1. **Model Tiering Strategy**:
   - **`gemini-3.8-flash`**: High-precision reasoning, multimodal document OCR (`receipt_scanner`), creative genre scouting and conversational editing (`video_editor`), structured tool-calling across all worker agents, and LLM-as-a-judge evaluation scoring.
   - **`gemini-3.1-flash-lite-image`**: 9:16 portrait outpainting and background synthesis for video frames.
   - **`gemini-omni-1.2-flash`**: Cinematic AI video animation and camera movement generation.
2. **Session State & Data Passing (`session.state`)**:
   - Rather than bloating prompt contexts with raw binary payloads or giant text tables across sub-agent transfers, agents communicate via workspace files and structured session state.
   - Staged media files (`assets/staged_media.mp4`, CSVs, generated posters) are managed per-agent and referenced through local storage paths.
3. **Progressive SSE Streaming**:
   - Real-time Server-Sent Events (`/run_sse`) stream function calls, function responses, and subagent state updates straight into the custom Svelte workspace.

---

## 🚀 Quick Start: Launch the Entire Workspace

### 1. Prerequisites & Installation

Make sure you have [uv](https://docs.astral.sh/uv/) (Python 3.12+) and Node.js (20+) installed:

```bash
# 1. Clone & enter repository
git clone https://github.com/aplachykau-git/gdg_agents.git
cd gdg_agents

# 2. Configure environment variables
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY / GOOGLE_CLOUD_PROJECT credentials

# 3. Install Python dependencies (locked) & Node packages
uv sync --locked
npm install
```

### 2. Launch All Services (Local Development)

To spin up the complete distributed multi-agent system (Video Editor A2A on port 8081, Receipt Scanner A2A on port 8082, Root Orchestrator on port 8080, and the Svelte 5 frontend on port 5173), run **a single command**:

```bash
# Recommended: start all A2A services, ADK web and frontend concurrently
make run-all

# Or using npm / script directly:
npm start
# or
./start_a2a_workspace.sh
```

### 🌐 Running Services

* **Frontend UI Dashboard**: [http://localhost:5173](http://localhost:5173)
* **Root Orchestrator Agent**: [http://localhost:8080](http://localhost:8080)
* **Video Editor A2A Service**: [http://localhost:8081/.well-known/agent-card.json](http://localhost:8081/.well-known/agent-card.json)
* **Receipt Scanner A2A Service**: [http://localhost:8082/.well-known/agent-card.json](http://localhost:8082/.well-known/agent-card.json)

---

### ☁️ Cloud Run & Firebase Production Deployment

GitHub Actions (`.github/workflows/deploy.yml`) runs `Lint & Test` on every push and pull request; production deploys are disabled on push and run only via manual `workflow_dispatch` on `main` with `deploy=true`. To build container images with Cloud Build and deploy all microservices to Google Cloud Run and Firebase Hosting locally:

```bash
# Deploy all Cloud Run services (community-root-agent, video-editor-a2a, receipt-scanner-a2a) and Firebase Hosting
make deploy

# Or provision & deploy infrastructure declaratively via Terraform
make tf-deploy

# Or deploy frontend-only updates to Firebase Hosting
make deploy-frontend
```

---

### Individual Service Commands (Optional)

```bash
# 1. Video Editor A2A Server (Port 8081)
npm run a2a:video

# 2. Receipt Scanner A2A Server (Port 8082)
npm run a2a:receipt

# 3. ADK workspace server with direct access to all agents (Port 8080)
npm run a2a:root

# 4. Svelte Frontend (Port 5173)
npm run dev
```

> `npm run a2a:root` serves the whole `agents/` workspace, so the frontend can open `root_agent` **or** any specialized sub-agent directly.

### 🧾 Google Docs & Google Drive Setup (Receipt Scanner)
The **Receipt Scanner** sub-agent processes receipt photos and multi-page PDFs (stitching PDF pages vertically and auto-orienting landscape receipt photos into a 2-per-row proof grid), clusters expenses semantically while preserving that exact order across the table and proofs, keeps template dropdown chips intact, resolves FX rates from NBP / Pekao / Frankfurter / Open ER (or asks for a manual rate rather than guessing), and generates native **Google Docs** directly in Google Drive using a **GCP Service Account** (`receipt-docs-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com`) or OAuth/ADC.
- To set up the Service Account in 1 minute and share your Google Doc template, see the [Setup Guide (Step 5)](docs/setup_guide.md#5-google-drive--google-docs-service-account-setup-cloud--native-google-docs).
- If offline or unconfigured, the agent automatically falls back to local `.docx` generation.

*For complete setup instructions, including Google Cloud authentication and template folder mapping, check out the [Setup Guide](docs/setup_guide.md).*

---

## 🎬 Video Editor Agent: Gemini Omni Flash

The **Video Editor sub-agent** automates the creation of high-quality, cinematic marketing video intros for event speakers. It combines generative AI models for portrait outpainting and video animation with a deterministic, code-driven GSAP + HTML vector layout engine:

### 🌟 Key Capabilities & Latest Features

1. **Multimodal Video Generation**:
   - **Gemini Omni Flash (`gemini-omni-1.2-flash`)**: Fast multimodal Image-to-Video generation via the Google AI Interactions API with unbroken single-shot camera dynamics, cinematic lighting, and realistic depth.

2. **Speaker Portrait 9:16 Outpainting**:
   - Outpaints static photos into vertical 9:16 aspect ratio using Gemini/Imagen, preserving face identity while expanding background context for seamless vertical video framing.

3. **Dynamic Timeline & Adaptive Composition**:
   - **Dynamic Duration Detection**: Probes media with `ffprobe` to automatically adjust the composition timeline between 8s (Omni video loops) and 10s (custom video uploads).
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
| `GOOGLE_GENAI_USE_VERTEXAI` | `1` (default) \| `0` | Uses Vertex AI credentials for Gemini calls when `1`; uses an API key when `0`. |
| `GOOGLE_API_KEY` | API key | Preferred API key when `GOOGLE_GENAI_USE_VERTEXAI=0`; also supported by the Omni video engine. |
| `GEMINI_API_KEY` | API key | Backwards-compatible fallback when `GOOGLE_API_KEY` is not set. |
| `VIDEO_ENGINE` | `omni` (default) | Selects the video generation model (`gemini-omni-1.2-flash`). |
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

## 🧪 Local Development, Testing & Operations

### Work without cloud costs
- `VIDEO_EDITOR_OFFLINE=true` — the video editor uses built-in fallback scenarios and returns the bundled
  sample video instead of calling Gemini Omni / HyperFrames (`VIDEO_EDITOR_OFFLINE_RENDER_SECONDS` simulates render time).
- `VITE_DEV_AUTH_BYPASS=true npm run dev --prefix frontend` — skip Google sign-in locally (ignored in production builds).

### Tests & Evaluations
- `uv run --locked python -m unittest discover tests` — no network, no Gemini: conversations run through the real ADK
  `Runner` with a scripted model (`tests/agent_harness.py`). Tests that hit real external APIs run only with `RUN_NETWORK_TESTS=1`.
- `npm test --prefix frontend` — UI payload adapters, scenario decks and stream merging (`node --test`, no extra deps).
- Offline deterministic evals: `make receipt-conversion-evals` (FX & totals) and `make receipt-grouping-evals` (semantic grouping & synced proof grid order).
- Live model/ADK evals (require Gemini/Vertex credentials): `make receipt-extraction-evals`, `make linkedin-judge-evals`, `make linkedin-evals`, `make video-editor-evals` (see [`docs/receipt_scanner_evals.md`](docs/receipt_scanner_evals.md)).

### Structured UI payloads
Cards in the UI (video, scenarios, LinkedIn variants, countdown post plan, event details, recognised receipts, QR code,
agenda, e-mail draft, meetup dates, documents) are rendered from a
`ui` payload produced by the backend (`agents/common/ui_payloads.py`), not guessed from the model's wording:
tool results carry `{"ui": {...}}`, text-only agents (LinkedIn, agenda) get it in `event.custom_metadata["ui"]`.
The old regex parsers live in `frontend/src/lib/legacy/textParsers.js` and are used only for sessions recorded before this.
New cards are built on `frontend/src/lib/ui/ResultCard.svelte` (header, body, actions) and routed in `StructuredCard.svelte`.

### Event details and social networks
Settings only hold the chapter name, video rendering and Google Drive. Everything about the event (date, website,
venue, highlights, hashtags, social profiles with links, countdown sequence) is set in the chat: tell the Social
Planner ("DevFest is on 10 October, our Instagram is instagram.com/gdgkrakow") or ask it to "show the event details".
It saves them with `update_event_profile` (`agents/common/event_profile_tools.py`) and shows an editable card; the
browser remembers the profile and sends it as `event_*` / `social_profiles` session state with every message
(`agents/common/event_profile.py` reads it). The website defaults to https://devfestkrakow.pl/.

### Countdown post plan
"Plan the countdown posts" builds dated slots from the countdown sequence (`agents/linkedin_post_generator/countdown.py`),
picks the networks per post (topic fit, max 3 LinkedIn posts a week, Instagram stories in the last days, short posts
on X / Threads / Bluesky / Mastodon), writes them in the team's house style and checks them against each network's
rules (length, hashtags, links vs "link in bio", wrong countdown numbers, `[LINK]` placeholders). The card exports
CSV for Google Sheets and an .ics with posting reminders.

### Persistent sessions
Locally nothing is needed: sessions are kept in SQLite files under `agents/<agent>/.adk/` and survive restarts.
In the cloud, `deploy/deploy_a2a_cloudrun.sh` reads a Postgres URI from the Secret Manager secret `session-service-uri`
if it exists. Any Postgres works: a free-tier external one (store e.g. `postgresql+asyncpg://user:pass@host/db` in the
secret) or Cloud SQL via `deploy/setup_sessions_db.sh` / `terraform apply -var enable_persistent_sessions=true` (paid).
Without the secret each Cloud Run service is pinned to one instance and sessions live until the container restarts.

### MCP server (use the studio from Claude, Gemini CLI or an IDE)
`agents/mcp_server.py` exposes the heavy tools over MCP, built on the same core as the ADK agents
(`agents/video_editor/video_card_service.py`: `generate_scenarios`, `render_card`):

| Tool | What it does |
|---|---|
| `propose_video_scenarios` | 5 cinematic scenarios (each with styles and a ready `creative_direction`) |
| `start_speaker_card_render` / `get_render_status` | render as a background job (1-3 min), poll for the result links |
| `process_registration_list` | clean/deduplicate an attendee CSV/XLSX, DOCX roster |
| `scan_receipt` | extract a receipt or invoice |
| `generate_qr_code` | rounded QR code for a link, saved as a flat SVG and a PNG |

- Local (stdio, the client starts it): `make mcp` or `uv run python -m agents.mcp_server`. The repo's `.mcp.json`
  registers it for Claude Code; other clients take the same `command`/`args` (run from the repo root).
- Remote: `MCP_AUTH_TOKEN=... uv run python -m agents.mcp_server --http --port 8090` (streamable HTTP at `/mcp`,
  every request needs `Authorization: Bearer <token>`; the server refuses to start without a token).
- `VIDEO_EDITOR_OFFLINE=true` works here too. Render jobs live in memory: they are lost when the server restarts.

### QR code generator
`agents/qr_code_generator/` turns a link into a rounded ("liquid") QR code: round dots and pills, smooth concave
corners, rounded corner eyes. Every code is saved as:
- **SVG**: one flat `<path>` in one colour (two when the eyes get their own colour), no gradients or images, so it
  scales for print and opens cleanly in Figma/Illustrator;
- **PNG**: 1024 px by default, rendered from the same geometry.

Options (just ask in chat): module colour, background colour or transparent background, eye colour.
Error correction is M, raised automatically when the code stays the same size; the quiet zone is the standard 4
modules. Files go to `agents/qr_code_generator/results/` (served at `/results/...` by the dev server) or to Cloud
Storage when `GCS_BUCKET_NAME` is set. The renderer lives in `qr_render.py` (`build_qr`) and is shared with the MCP
server; `tests/test_qr_code_generator.py` decodes the generated PNGs with zxing-cpp to make sure they scan.

### Models & logging
- Models are configured in `agents/gemini_config.py`: `GEMINI_MODEL` for all text roles, or per role `MODEL_<ROLE>`
  (e.g. `MODEL_VIDEO_EDITOR`, `MODEL_ROOT_AGENT`, `MODEL_VIDEO_OUTPAINT`).
- `LOG_LEVEL` controls verbosity; on Cloud Run logs are JSON lines with proper severity (`LOG_FORMAT=json` forces it locally).

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
