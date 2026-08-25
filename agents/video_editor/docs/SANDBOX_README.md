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
   cd agents/video_editor/
   npm install
   cd ../../
   ```

3. **Configure Environment:**
   All configuration settings are managed directly in the project root `.env` file (no separate credentials file is needed as the system uses your GCP ADC credentials naturally).

---

## 🤖 Running the AI Agent with ADK Web

Google Antigravity provides a web UI to test and interact with your agent locally. Launch the root agent:

```bash
source .venv/bin/activate
adk web --port 8000 agents/root_agent
```

1. Open `http://localhost:8000` in your web browser.
2. Select the main **root_agent** agent.
3. Upload a speaker portrait or a custom background video in the chat, and describe the speaker details.
4. The root agent will delegate to `video_editor`, which outpaints, animates, and renders the cards!

---

## 💻 Developer Commands (From Project Root)

You can run individual HyperFrames compiler tasks directly via root npm scripts:

```bash
# Start local dev server with visual preview (scrub timeline at http://localhost:3000)
npm run video:dev

# Run linter, Chrome validation and layout checks
npm run video:check

# Render ordinary 1080p video file
npm run video:render
```

---

## ⚙️ Configuration Overrides (`.env`)

You can toggle video generation engines and rendering outputs in your `.env` file:

```ini
# Select video generation engine: "veo" (Vertex AI Veo 3.1) or "omni" (Gemini Omni Flash preview)
VIDEO_ENGINE=veo

# Set to "false" to bypass AI video API calls during testing (uses static placeholder assets instead)
ENABLE_VIDEO_GENERATION=false

# Toggle individual render pipelines (true/false)
RENDER_4K=true
RENDER_ORDINARY=true
RENDER_GIF=true
```
