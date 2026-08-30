# Environment Variable Reference

Copy `.env.example` to `.env` and fill in the required values. Never commit `.env` to Git.

---

## 1. Gemini & Vertex AI Backend

| Variable | Default | Required | Description |
|:---|:---|:---:|:---|
| `GOOGLE_GENAI_USE_VERTEXAI` | `1` | Yes | `1` — route all Gemini calls through Vertex AI (ADC/workload identity). `0` — use Gemini Developer API key instead. |
| `GOOGLE_CLOUD_PROJECT` | — | Vertex only | GCP project ID. Required when `GOOGLE_GENAI_USE_VERTEXAI=1`. |
| `GOOGLE_CLOUD_LOCATION` | `global` | Vertex only | Vertex AI region (e.g. `us-central1`). |
| `GOOGLE_API_KEY` | — | API key mode | Gemini Developer API key. Required when `GOOGLE_GENAI_USE_VERTEXAI=0`. Also used by the Omni video engine regardless of backend mode. |
| `GEMINI_API_KEY` | — | — | Fallback alias for `GOOGLE_API_KEY`. Both are accepted; `GOOGLE_API_KEY` takes precedence. |

---

## 2. Google Drive & Docs Integration (Receipt Scanner)

| Variable | Default | Required | Description |
|:---|:---|:---:|:---|
| `GOOGLE_DRIVE_FOLDER_ID` | — | No | Target Google Drive folder ID for expense report exports. Can also be provided per-session via the frontend Settings modal. |
| `GOOGLE_DOCS_TEMPLATE_ID` | — | No | Google Docs template document ID used when generating expense reports. Falls back to a blank doc if unset. |
| `GOOGLE_AUTH_METHOD` | `adc` | Cloud only | Authentication method for Drive/Docs API calls. `adc` uses workload identity (Cloud Run). Not typically set in local `.env`. |

---

## 3. Community & Branding

| Variable | Default | Required | Description |
|:---|:---|:---:|:---|
| `COMMUNITY_NAME` | `Community` | No | Community name injected into agent instructions and UI branding (e.g. `Krakow`, `Warsaw`). Affects LinkedIn hashtag generation (`#GDGKrakow`), agenda copy, and event planner search queries. |

---

## 4. Video Editor

| Variable | Default | Required | Description |
|:---|:---|:---:|:---|
| `VIDEO_ENGINE` | `veo` | No | Video generation model. `veo` — Vertex AI Veo 3.1 (`veo-3.1-fast-generate-001`), requires `GOOGLE_GENAI_USE_VERTEXAI=1`. `omni` — Gemini Omni Flash (`gemini-omni-1.1-flash`), works with API key mode. |
| `ENABLE_VIDEO_GENERATION` | `false` | No | Set to `true` to enable AI video generation (Veo or Omni). When `false`, the compositor uses a local placeholder video — useful for layout dry-runs without consuming GPU quota. |
| `RENDER_ORDINARY` | `true` | No | Render a 1080p Full HD MP4 output. |
| `RENDER_GIF` | `true` | No | Render an animated GIF output via FFmpeg (requires `ffmpeg` on PATH). |
| `RENDER_4K` | `false` | No | Render a 4K Ultra HD MP4 output. Disabled by default due to longer render times. |
| `VIDEO_EDITOR_PROPOSE_TYPO_CORRECTIONS` | `true` | No | When `true`, the agent inspects talk title and role/company for obvious spelling mistakes and proposes corrections before rendering. Set to `false` to disable. |

---

## 5. Microservice & A2A Networking

| Variable | Default | Required | Description |
|:---|:---|:---:|:---|
| `VIDEO_AGENT_A2A_URL` | — | No | Full URL to the Video Editor A2A service. When set, overrides `VIDEO_AGENT_HOST` + `VIDEO_AGENT_PORT`. Use for Cloud Run deployments (e.g. `https://video-editor-a2a-xxxx.a.run.app`). |
| `VIDEO_AGENT_HOST` | `localhost` | No | Hostname for the Video Editor A2A service (local dev). |
| `VIDEO_AGENT_PORT` | `8081` | No | Port for the Video Editor A2A service (local dev). |
| `VIDEO_AGENT_PROTOCOL` | `http` | No | Protocol for the Video Editor A2A service. Set to `https` for remote deployments if not using `VIDEO_AGENT_A2A_URL`. |
| `RECEIPT_AGENT_A2A_URL` | — | No | Full URL to the Receipt Scanner A2A service. When unset, the root agent falls back to the local in-process receipt agent. Required in Cloud Run deployments. |
| `RECEIPT_AGENT_HOST` | `localhost` | No | Hostname for the Receipt Scanner A2A service (local dev). |
| `RECEIPT_AGENT_PORT` | `8082` | No | Port for the Receipt Scanner A2A service (local dev). |
| `GCS_BUCKET_NAME` | — | Cloud only | GCS bucket name for storing rendered video assets, staged media, and generated documents. Set automatically by Terraform. |

---

## 6. Frontend (Vite — `VITE_` prefix)

These variables are compiled into the frontend bundle at build time. Set them in `frontend/.env` or inject at CI build time.

| Variable | Default | Required | Description |
|:---|:---|:---:|:---|
| `VITE_API_URL` | — | Production | Root agent Cloud Run URL. When unset, the frontend uses Firebase Hosting rewrites (local dev proxies to `localhost:8080`). |
| `VITE_FIREBASE_PROJECT_ID` | `gdg-agents-6b59a` | No | Firebase project ID. Override for a custom Firebase project. |
| `VITE_FIREBASE_APP_ID` | _(bundled)_ | No | Firebase app ID. |
| `VITE_FIREBASE_API_KEY` | _(bundled)_ | No | Firebase Web API key. |
| `VITE_FIREBASE_AUTH_DOMAIN` | _(bundled)_ | No | Firebase Auth domain. |
| `VITE_FIREBASE_STORAGE_BUCKET` | _(bundled)_ | No | Firebase Storage bucket. |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | _(bundled)_ | No | Firebase Cloud Messaging sender ID. |
| `VITE_FIREBASE_PROJECT_NUMBER` | _(bundled)_ | No | Firebase project number. |
| `VITE_RECAPTCHA_SITE_KEY` | — | No | reCAPTCHA v3 site key for Firebase App Check. When set, App Check is initialized and bot protection is active. Also accepted as `VITE_FIREBASE_APP_CHECK_KEY`. |
| `VITE_STUDIO_SA_EMAIL` | — | No | Service account email shown in the Drive Access banner (`community-studio-runtime@<project>.iam.gserviceaccount.com`). Injected at build time from `terraform output service_account_email`. |
