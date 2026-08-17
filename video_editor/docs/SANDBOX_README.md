# Live Speaker Avatars: AI Video Editor Agent & Render Sandbox

This project features the **Video Editor Agent**, an intelligent AI agent built on the **Google Antigravity (ADK 2.0)** SDK. The agent automates the creation of premium, cinematic video intros for speakers by outpainting static portrait photos to 9:16 using Gemini, animating them via Google Veo 3.1, custom-styling a responsive GSAP vector layout, and compiling the output concurrently into high-quality formats (1080p, 4K, and animated GIFs).

---

## 🚀 Getting Started

### 📋 Prerequisites

To run this sandbox and agent, ensure you have the following installed:

1. **Python 3.10+** (to run the AI agent and Google ADK)
2. **Node.js v22+** (to run the HyperFrames compiler in headless Chrome)
3. **FFmpeg** (Optional but highly recommended: automatically detected in system `PATH` for stripping audio and converting videos to GIF).

## 🛠️ Installation & Setup

1. **Python dependencies** are already handled in the main project `requirements.txt`.
2. **Install Node.js dependencies** for the HyperFrames rendering compiler:

   ```bash
   cd video_editor/
   npm install
   cd ../
   ```

3. **Configure Environment:**
   All configuration settings are managed directly in the root agent's environment file `root_agent/.env` (no separate credentials file is needed as the system uses your GCP ADC credentials naturally).

---

## 🤖 Running the AI Agent with ADK Web

Google Antigravity provides a web UI to test and interact with your agent locally. Launch the root agent:

```bash
cd root_agent
../.venv/bin/adk web --port 8000
```

1. Open `http://localhost:8000` in your web browser.
2. Select the main **root_agent** agent.
3. Upload a speaker portrait or a custom background video in the chat, and describe the speaker details.
4. The root agent will delegate to `video_editor`, which outpaints, animates, and renders the cards!

---

## 💻 Manual Developer Commands (Inside the Agent Folder)

You can run individual HyperFrames compiler tasks directly inside `video_editor/`:

```bash
cd video_editor/

# Start local dev server with hot-reload and visual preview (scrub timeline at http://localhost:3000)
npm run dev

# Run linter, Chrome validation and layout checks
npm run check

# Render ordinary 1080p video file
npm run render

# Publish composition and get a shareable link
npm run publish
```

---

## ⚙️ Configuration Overrides (`.env`)

You can toggle rendering outputs and dry-run modes inside your `.env` file:

```ini
# Set to "false" to bypass Veo API calls during testing (uses static placeholder assets instead)
ENABLE_VIDEO_GENERATION=false

# Toggle individual render pipelines (true/false)
RENDER_ORDINARY=true
RENDER_GIF=true
RENDER_4K=true
```
