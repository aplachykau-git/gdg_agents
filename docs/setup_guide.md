# 🚀 GDG Agentic Workspace - Setup & Operations Guide

Welcome to the comprehensive setup and operations guide for the **GDG Agentic Workspace**. This project is a multi-agent orchestration workspace built using the [Google Agent Development Kit (ADK) 2.0](https://adk.dev/) in Python (powered by Vertex AI and Gemini models) paired with a high-performance, responsive **Svelte + Vite** custom frontend.

---

## 🏗️ System Architecture

The project consists of three main layers:

```mermaid
graph TD
    A[Custom Svelte Frontend <br> port 5173] -->|API Proxy| B[FastAPI Backend / ADK <br> port 8080]
    B --> C[Root Orchestrator Agent <br> root_agent]
    C --> D[Receipt Scanner <br> receipt_scanner]
    C --> E[Live Video Editor <br> video_editor]
    C --> F[LinkedIn Planner <br> linkedin_post_generator]
    C --> G[Registrations Manager <br> registration_manager]
    C --> H[Event Scheduler <br> event_planner]
    C --> I[Agenda Formatter <br> agenda_generator]
```

1. **Custom Svelte Frontend (`frontend/`)**: A dark-themed, premium workspace that provides a chat interface, real-time status ticker for the agents, and capability highlights.
2. **Root Orchestrator Agent (`root_agent/`)**: The main coordinating Python agent that receives user requests, determines the correct domain, and delegates tasks to the appropriate specialized sub-agents.
3. **Sub-Agents Core**: Six specialized sub-agents covering receipts/expense reporting, speaker video generation, social media management, guest lists, meetup scheduling, and agendas.

---

## 📋 Prerequisites

Ensure you have the following installed on your machine:
* **Python 3.10+** (to run ADK and agent packages)
* **Node.js v22+** (to run the custom Svelte frontend and the HyperFrames render server)
* **FFmpeg** (strongly recommended, used for video rendering and processing tasks)
* **Google Cloud SDK / CLI** (for Vertex AI authentication)

---

## 🛠️ Step-by-Step Setup

Follow these steps to set up both the backend and frontend environments.

### 1. Python Environment (Backend)

Initialize a virtual environment and install backend dependencies in editable mode:

```bash
# 1. Initialize a virtual environment
python3 -m venv .venv

# 2. Activate the environment
source .venv/bin/activate

# 3. Install requirements
pip install -r requirements.txt

# 4. Install the workspace packages in editable mode
pip install -e .
```

### 2. Node.js Environment (Frontend & Video Editor)

Install the Node packages for both the Svelte workspace and the rendering engine:

```bash
# Install Svelte UI dependencies
cd frontend
npm install
cd ..

# Install HyperFrames rendering dependencies
cd video_editor
npm install
cd ..
```

### 3. Google Cloud Authentication

Authenticate your local environment with Google Cloud to grant Vertex AI API access:

```bash
bash <(curl -sSL https://storage.googleapis.com/cloud-samples-data/adc/setup_adc.sh)
```
*Provide your GCP Project ID (e.g., `gdg-agents-496611`) when prompted and complete authentication in your browser.*

### 4. Configuration Settings (.env)

The root agent requires a `.env` file to be present in the project root directory. You can use the template [.env.example](file:///Users/aplachykau/Experiments/gdg_krakow_tool/.env.example) to create it:

```bash
# Copy the example configuration to .env
cp .env.example .env
```

Open `.env` and fill in the following parameters:
- `GEMINI_API_KEY`: Your private API key from [Google AI Studio](https://aistudio.google.com/).
- `GOOGLE_GENAI_USE_VERTEXAI`: Set to `1` to run via Vertex AI endpoints, or `0` for public API.
- `GOOGLE_CLOUD_PROJECT`: Your GCP Project ID from [Google Cloud Console](https://console.cloud.google.com/).
- `GOOGLE_CLOUD_LOCATION`: The GCP region/location (e.g. `europe-central2`).
- `GOOGLE_DRIVE_FOLDER_ID`: The ID of your target Google Drive folder (found in the folder's URL).
- `ENABLE_VIDEO_GENERATION`: Set to `true` to run speaker video intro renders (costs tokens), or `false` for layout-only dry-runs. 
  > [!WARNING]
  > Video generation using Google Veo is computationally expensive and incurs high token costs. It is highly recommended to keep this `false` during local development and layout testing. Instead, generate the video manually using the **Genkit Flow tool** (UI), select the vertical video you prefer, and upload it manually to save tokens.

### 5. Customizing the Expense Report Google Doc Template

The **Receipt Scanner** sub-agent compiles reports by copying a Google Doc template and populating placeholders. By default, it uses a shared, read-only template.

To customize the report template (e.g., adding your own styling, custom tables, headers, or organizational details):
1. Open the default template: [Google Docs Template](https://docs.google.com/document/d/1nkT3N6ovmmBJYDK9S9oRRaOZ6sCQkAwve58y7sS2eOw/edit).
2. Create a copy of it in your own Google Drive (**File -> Make a copy**).
3. Modify the copied document as you like (keep the existing placeholder tags like `{{APPROVED}}` and `{{EXPENSES_TABLE}}` where you want the dynamic content to be inserted).
4. Extract the Document ID from the URL of your new document (e.g., `https://docs.google.com/document/d/<YOUR_DOCUMENT_ID>/edit`).
5. Open the local file [Expense_report_template.gdoc](file:///Users/aplachykau/Experiments/gdg_krakow_tool/receipt_scanner/assets/Expense_report_template.gdoc) and replace the `"doc_id"` value with your new document ID:
   ```json
   {
     "doc_id": "YOUR_NEW_DOCUMENT_ID",
     "resource_key": ""
   }
   ```

---

## 🚀 Running the Entire Project

To run the complete system with the custom Svelte frontend talking to the ADK backend agent, you need to spin up two processes in separate terminal sessions:

### Terminal 1: Launch Backend (ADK FastAPI Server)

The backend agent server must run on port `8080` (as Vite is configured to proxy all API requests to `127.0.0.1:8080`).

```bash
# Make sure virtual environment is active
source .venv/bin/activate

# Run the ADK web server mapping all local agents in the current folder
adk web --port 8080 .
```

### Terminal 2: Launch Frontend (Svelte Dev Server)

```bash
cd frontend
npm run dev
```
*This starts the Vite server (typically at `http://localhost:5173`).*

### Open the Application

Now, open your browser and navigate to:
👉 **[http://localhost:5173](http://localhost:5173)**

Here you will find the **Advanced Agentic Workspace** where you can select the active agent, start new chat sessions, type requests, and drag-and-drop receipts or participant rosters directly.

---

## 🛠️ Alternative & Diagnostic Operations

### 1. Using the Default ADK Developer UI
If you want to use the default web playground provided out-of-the-box by ADK:
```bash
source .venv/bin/activate
cd root_agent
adk web --port 8000
```
Open **`http://localhost:8000`** in your browser.

### 2. Testing Receipt Scanner via CLI
You can bypass web servers entirely to test the receipt OCR scanner and currency converter using the CLI:
```bash
source .venv/bin/activate
python receipt_scanner/test_runner.py
```

### 3. HyperFrames Development & Preview Sandbox
To preview the video composition layout, debug GSAP timelines, or check visual spacing:
```bash
cd video_editor

# Run local dev server with hot-reload and visual preview (scrub timeline at http://localhost:3000)
npm run dev

# Run linter, Chrome validation and layout checks
npm run check

# Render composition to an MP4 video file locally
npm run render
```

---

## 🧹 Code Quality & Formatter

Before pushing any Python updates, make sure your code aligns with our Ruff styling guidelines (line-length is capped at `120` characters):

```bash
# Format Python files
ruff format .

# Check for lint errors and warnings
ruff check .

# Apply auto-fixes
ruff check --fix .
```
