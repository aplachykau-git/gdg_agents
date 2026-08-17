# GDG Agentic Workspace (ADK)

This project is a multi-agent system built on the [Google Agent Development Kit (ADK) 2.0](https://adk.dev/), written in Python. It leverages the capabilities of Vertex AI (Gemini and Veo) models to automate events operations, document templates compilation, receipt scanning, scheduling conflicts analysis, and social media posting.

---

## 🏗️ Project Structure

The workspace is split into decoupled modules for high maintainability, portability, and independent development:

* **`root_agent/`** — The main coordinating Root Agent (`gemini-2.5-flash`). It acts as an intelligent router delegating requests to specialized sub-agents.
* **`receipt_scanner/`** — Sub-agent (`gemini-2.5-pro`) for high-precision receipt and invoice OCR, currency conversion, and Google Docs/Drive template compilation.
* **`video_editor/`** — Sub-agent (`gemini-2.5-flash`) for speaker card outpainting (Gemini), video animation (Google Veo 3.1), and 4K layout compilation.
* **`linkedin_post_generator/`** — Sub-agent (`gemini-2.5-flash`) for drafting and styling event recap posts and speaker announcements for LinkedIn.
* **`registration_manager/`** — Sub-agent (`gemini-2.5-flash`) for guest registration sorting, capacity verification, and organizer list management.
* **`event_planner/`** — Sub-agent (`gemini-2.5-flash`) for scanning calendars (Luma, Meetup.com) to find conflict-free, holiday-safe event dates.
* **`agenda_generator/`** — Sub-agent (`gemini-2.5-flash`) for compiling and formatting clean event agendas with speaker timelines.
* **`office_secretary/`** — Sub-agent (`gemini-2.5-flash`) for drafting polite key access and Event Hub reservation request letters.
* **`frontend/`** — A custom **Svelte + Vite** single-page application providing a premium, custom dashboard interface for the entire workspace.
* **`docs/`** — Project documentation and guides (see [Setup Guide](file:///Users/aplachykau/Experiments/gdg_krakow_tool/docs/setup_guide.md)).

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

## 🚀 Quick Start: Launch the Entire Project

To spin up the complete application (both the Python agent server and the custom Svelte frontend), run the following:

### 1. Start the ADK Agent Backend (Port 8080)

Make sure your Python virtual environment is active, then run:

```bash
# From project root
source .venv/bin/activate
adk web --port 8080 .
```

### 2. Start the Svelte Dev Server (Port 5173)

In a separate terminal window:

```bash
# Go to frontend folder
cd frontend

# Install Node dependencies (first time only)
npm install

# Start the Vite server
npm run dev
```

### 3. Open the UI

Go to **[http://localhost:5173](http://localhost:5173)** in your browser to interact with the workspace!

*For detailed setup instructions, including Google Cloud authentication and template folder mapping, check out the [Setup Guide](file:///Users/aplachykau/Experiments/gdg_krakow_tool/docs/setup_guide.md).*

---

## 🎬 Video Editor Agent & HyperFrames Sandbox

The **Video Editor sub-agent** automates the creation of high-quality, cinematic marketing video intros for event speakers. It processes portrait photos by outpainting them to 9:16 aspect ratio using Gemini, animating them via Google Veo 3.1, custom-styling a responsive GSAP vector layout, and compiling the outputs (1080p, 4K, and animated GIFs) in parallel.

### Manual Developer Commands (Inside `video_editor/`)

You can run individual HyperFrames compiler tasks directly inside `video_editor/` to preview, check, and render templates:

```bash
cd video_editor/

# Install rendering dependencies (first time only)
npm install

# Start local dev server with hot-reload and visual preview (scrub timeline at http://localhost:3000)
npm run dev

# Run linter, Chrome validation, and layout checks
npm run check

# Render ordinary 1080p video file
npm run render

# Publish composition and get a shareable link
npm run publish
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
