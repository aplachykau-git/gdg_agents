# Speaker Card Template Customization & Embedding Guide

This guide documents the layout specs, customization steps, and embedding instructions for the **Live Speaker Avatars** template.

---

## 📐 Template Design System

* **Resolution:** 1920 × 1080 px (Landscape)
* **Duration:** 10.0 seconds (30 FPS deterministic timeline)
* **Fonts:** Google Sans (Google Fonts)
* **Visual Coordinates:**
  * **Video Frame Bounds:** `left: 127px`, `top: 130px`, `width: 585px`, `height: 821px` (`border-radius: 43px`).
  * **Text Container (`.text-group`):** `left: 822px`, `top: 520px`, `width: 971px`, `height: 431px` (Bottom border aligned with video frame base).

---

## 🛠️ Step-by-Step Template Customization

To manually customize a card template, edit the centralized config block at the bottom of [index.html](file:///Users/aplachykau/Experiments/gdg_krakow_tool/video_editor/index.html):

```javascript
const CARD_CONFIG = {
  title: "How To Create AI Videos That Actually Work", // Typewriter Title (max 80 chars)
  name: "Yuliya Algeri",                               // Speaker Name (max 50 chars)
  position_company: "Designer, DDD Systems"           // Role / Company (max 80 chars)
};
```

### Critical Rules

1. **Dynamic Font Autoscaling:** The title font size adapts dynamically to fit within exactly 2 lines. Do not manually edit the text dimensions.
2. **Video Cutout Mask:** The video frame is masked by a rounded SVG cutout at `z-index: 10`. To change the video position, both the `<video>` tag CSS and the SVG path cutout coordinates must match exactly.
3. **Determinism:** Do not use `Math.random()`, `Date.now()`, or external network fetches. All animations must be registered on the paused GSAP timeline: `window.__timelines["video_editor"] = tl`.

---

## 📦 How this Agent is Embedded in the Parent System

The `video_editor/` folder is integrated directly at the project root, sitting alongside `receipt_scanner/` and `root_agent/` as a sibling sub-agent.

### 1. Configuration & Root Agent Setup

The parent root agent loaded in `root_agent/agent.py` imports and registers this agent:

```python
from video_editor.agent import root_agent as video_agent

root_agent = Agent(
    ...
    sub_agents=[receipt_agent, video_agent]
)
```

### 2. Environment Variables (.env)

The environment parameters are set up in the main `root_agent/.env` file:

```ini
# --- Video Editor Configurations ---
ENABLE_VIDEO_GENERATION=true
RENDER_ORDINARY=true
RENDER_GIF=true
RENDER_4K=true
```

### 3. Keyless Authentication via ADC

In the integrated setup, `video_editor/tools/media_tools.py` will automatically fall back to **Application Default Credentials (ADC)** if no `GEMINI_API_KEY` is present. This eliminates the need for separate, hardcoded service account keys, allowing it to naturally reuse your active GCP project authentication:

```python
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    client = genai.Client(api_key=api_key)
else:
    client = genai.Client()  # Resolves ADC/Vertex AI naturally
```

Since the agent sets its internal shell subprocess execution directory dynamically (`cwd=BASE_DIR`), all compiler commands (`npm run render`, `npx hyperframes validate`) execute flawlessly inside the nested folder, completely independent of where the main root agent server was started!
