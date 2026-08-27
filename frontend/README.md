# Community AI Studio - Custom Frontend

This is the Svelte-based frontend application for **Community AI Studio**. It provides a modern, responsive dashboard that interacts with backend agents to help orchestrate community workflows.

---

## 🚀 Running the Frontend

To run this application locally, you must first start the ADK backend server, then start Vite:

### 1. Start backend agent (in separate terminal)
```bash
# From project root
uv run --locked adk web --port 8080 agents
```

### 2. Install dependencies & launch dev server
```bash
# Navigate to this folder
cd frontend

# Install Node dependencies
npm install

# Run the dev server
npm run dev
```

The app will be served at **[http://localhost:5173](http://localhost:5173)**.

---

## ⚙️ Technical Details

### Proxy Configuration
Vite is configured to proxy API requests to the Python ADK backend at `http://127.0.0.1:8080`.
The configuration can be found and modified in [vite.config.js](./vite.config.js):
```javascript
server: {
  proxy: {
    '/list-apps': { target: 'http://127.0.0.1:8080', ... },
    '/run': { target: 'http://127.0.0.1:8080', ... },
    '/run_sse': { target: 'http://127.0.0.1:8080', ... },
    '/apps': { target: 'http://127.0.0.1:8080', ... }
  }
}
```

### State Management
State variables are managed in Svelte 5 runes (`$state` and `$derived`) inside [App.svelte](./src/App.svelte).
It handles:
* Chat session history fetches
* Real-time streaming chunk rendering
* Multi-variant option parsed views
* File upload base64 encoding (for receipts, photos, and csv rosters)
