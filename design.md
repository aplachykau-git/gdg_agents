# Design System Specification: GDG Agents

> **Version:** 1.0.0  
> **Target Platform:** Web Portal / Svelte 5 + Vite  
> **Aesthetic & Baseline:** Material Design 3 (M3 Expressive)  
> **Status:** Ready for Engineering Implementation  

---

## 1. Design Tokens

### 1.1 Color Palette & Theme Tokens

The color system is built on Material 3 principles with a content-first focus, seamless dark/light mode switching, and clean, solid brand accents.

```css
:root {
  /* =========================================================================
   * Clean Brand Accents
   * ========================================================================= */
  --gemini-primary: #1a73e8;
  --gemini-primary-hover: #1557b0;
  --gemini-active-glow: rgba(26, 115, 232, 0.12);
  --gemini-subtle-border: rgba(26, 115, 232, 0.25);
}

/* =========================================================================
 * Dark Mode Tokens (Default Canvas)
 * ========================================================================= */
[data-theme="dark"], :root:not([data-theme="light"]) {
  /* Backgrounds & Surfaces */
  --bg-app: #131314;               /* Dark canvas background */
  --bg-surface: #1e1f20;           /* Sidebars, cards, and containers */
  --bg-surface-elevated: #282a2c;  /* Elevated elements (hover states, icon boxes) */
  --bg-surface-variant: #333538;   /* Active states, user message bubbles */
  --bg-input: #1e1f20;             /* Prompt input background */
  --bg-input-focus: #282a2c;       /* Prompt input focused background */

  /* Text & Content */
  --text-primary: #e3e3e3;         /* Primary text (high emphasis) */
  --text-secondary: #c4c7c5;       /* Secondary text, captions, agent descriptions */
  --text-tertiary: #8e918f;        /* Placeholders, disabled states, metadata */
  --text-inverse: #131314;         /* Inverted text on solid blue buttons */

  /* Borders & Dividers */
  --border-subtle: #2d2f31;        /* Default subtle border */
  --border-medium: #444746;        /* Pronounced border (hover states) */
  --border-focus: #8ab4f8;         /* Focus ring color */

  /* Primary Brand & Accents */
  --primary-accent: #8ab4f8;       /* Blue (Light tint for dark mode) */
  --primary-accent-hover: #aecbfa;
  --primary-accent-container: #004a77;
  --primary-accent-text: #c2e7ff;
  
  /* Status Colors */
  --status-success: #81c995;
  --status-warning: #fdd663;
  --status-error: #f28b82;
  --status-info: #8ab4f8;

  /* Shadows (M3 Elevation) */
  --shadow-elevation-1: 0 1px 3px 1px rgba(0, 0, 0, 0.25), 0 1px 2px 0 rgba(0, 0, 0, 0.30);
  --shadow-elevation-2: 0 2px 6px 2px rgba(0, 0, 0, 0.25), 0 1px 2px 0 rgba(0, 0, 0, 0.30);
  --shadow-elevation-3: 0 4px 8px 3px rgba(0, 0, 0, 0.25), 0 1px 3px 0 rgba(0, 0, 0, 0.30);
  --shadow-glow: 0 0 20px rgba(66, 133, 244, 0.12);
}

/* =========================================================================
 * Light Mode Tokens
 * ========================================================================= */
[data-theme="light"] {
  /* Backgrounds & Surfaces */
  --bg-app: #f8fafd;
  --bg-surface: #ffffff;
  --bg-surface-elevated: #f0f4f9;
  --bg-surface-variant: #e1e3e1;
  --bg-input: #ffffff;
  --bg-input-focus: #f0f4f9;

  /* Text & Content */
  --text-primary: #1f1f1f;
  --text-secondary: #444746;
  --text-tertiary: #747775;
  --text-inverse: #ffffff;

  /* Borders & Dividers */
  --border-subtle: #e0e2e0;
  --border-medium: #c4c7c5;
  --border-focus: #1a73e8;

  /* Primary Brand & Accents */
  --primary-accent: #1a73e8;
  --primary-accent-hover: #1557b0;
  --primary-accent-container: #d3e3fd;
  --primary-accent-text: #041e49;

  /* Status Colors */
  --status-success: #1e8e3e;
  --status-warning: #f9ab00;
  --status-error: #d93025;
  --status-info: #1a73e8;

  /* Shadows (M3 Elevation) */
  --shadow-elevation-1: 0 1px 2px 0 rgba(60, 64, 67, 0.3), 0 1px 3px 1px rgba(60, 64, 67, 0.15);
  --shadow-elevation-2: 0 1px 2px 0 rgba(60, 64, 67, 0.3), 0 2px 6px 2px rgba(60, 64, 67, 0.15);
  --shadow-elevation-3: 0 4px 8px 3px rgba(60, 64, 67, 0.15), 0 1px 3px 0 rgba(60, 64, 67, 0.30);
  --shadow-glow: 0 0 16px rgba(26, 115, 232, 0.12);
}
```

---

### 1.2 Typography System

Typography relies on **Google Sans** with progressive fallbacks to **Inter**, **Outfit**, and system font stacks.

```css
:root {
  --font-family-base: 'Google Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-family-display: 'Google Sans Display', 'Google Sans', 'Outfit', sans-serif;
  --font-family-mono: 'Google Sans Mono', 'Fira Code', 'JetBrains Mono', 'Roboto Mono', monospace;

  /* Type Scale */
  --font-size-display-lg: 2.25rem;  /* 36px | Line-height: 44px | Bold (700) */
  --font-size-display-md: 1.75rem;  /* 28px | Line-height: 36px | SemiBold (600) */
  --font-size-title-lg: 1.375rem;   /* 22px | Line-height: 28px | Medium (500) */
  --font-size-title-md: 1rem;       /* 16px | Line-height: 24px | Medium (500) */
  --font-size-body-lg: 1rem;        /* 16px | Line-height: 24px | Regular (400) */
  --font-size-body-md: 0.875rem;    /* 14px | Line-height: 20px | Regular (400) */
  --font-size-body-sm: 0.75rem;     /* 12px | Line-height: 16px | Regular (400) */
  --font-size-label: 0.6875rem;     /* 11px | Line-height: 14px | Medium (500) - Uppercase */
}
```

---

### 1.3 Border Radii & Shape System (M3 Expressive)

A defining visual characteristic of Google AI Studio and Material 3 Expressive is generous corner roundings for inputs, floating surfaces, and message cards.

```css
:root {
  --radius-xs: 4px;      /* Badges, small tags */
  --radius-sm: 8px;      /* Toolbar buttons, dropdown items */
  --radius-md: 12px;     /* Config cards, code blocks */
  --radius-lg: 16px;     /* Dialogs, modals, drawer panels */
  --radius-xl: 24px;     /* Floating prompt container, message cards */
  --radius-2xl: 32px;    /* Large interactive containers, filter chips */
  --radius-pill: 9999px; /* Toggle buttons, avatars, pill badges */
}
```

---

## 2. Global Layout (Streamlined Workstation Grid)

The interface implements a responsive two-column workstation layout:

```
+-------------------------------------------------------------------------------------------------------+
|  HEADER (Top App Bar): Logo [GDG Agents] | Active Agent Selector | Capabilities | Theme Toggle        |
+-------------------+-----------------------------------------------------------------------------------+
|                   |                                                                                   |
|   LEFT SIDEBAR    |                        CENTRAL WORKSPACE ZONE                                     |
|  (260px - 300px)  |                        (Flex-grow: 1, full remaining width)                       |
|                   |                                                                                   |
| - New Prompt (+)  |  +-----------------------------------------------------------------------------+  |
| - Prompt History  |  | Informative Agent Catalog & Workflow Hub / Chat Message Stream              |  |
| - Session Actions |  +-----------------------------------------------------------------------------+  |
| - Agent Quota/Ping|  | Floating Expandable Prompt Input Bar with Multimodal Attachment Support     |  |
|                   |  +-----------------------------------------------------------------------------+  |
+-------------------+-----------------------------------------------------------------------------------+
```

> **Note on Model Configuration:** Hyperparameters (Temperature, Top-P, Top-K, and Output Encodings) are pre-calibrated and managed server-side by each specialized agent according to its specific task constraints (e.g., deterministic regex and JSON schema enforcement for OCR/Calendar, high-creative parameters for LinkedIn copy and video prompts).

### 2.1 CSS Grid Specification

```css
.ai-studio-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  grid-template-rows: 56px calc(100vh - 56px);
  grid-template-areas:
    "header header"
    "sidebar main";
  height: 100vh;
  width: 100vw;
  background-color: var(--bg-app);
  color: var(--text-primary);
  overflow: hidden;
}

@media (max-width: 768px) {
  .ai-studio-layout {
    grid-template-columns: 1fr;
    grid-template-areas:
      "header"
      "main";
  }
}
```

---

## 3. Key UI Components

### 3.1 Floating Prompt Input Box

The central interactive element of Google AI Studio:

```html
<div class="prompt-box-container">
  <div class="prompt-box">
    <!-- Top toolbar: media attachments & token telemetry -->
    <div class="prompt-toolbar-top">
      <button class="chip-btn" title="Add Media/Files">
        <Plus size="16" /> Add files
      </button>
      <div class="token-counter">
        <span class="token-number">128</span> / 1,048,576 tokens
      </div>
    </div>

    <!-- Multi-line auto-expanding textarea -->
    <textarea 
      class="prompt-textarea" 
      placeholder="Type something, or press Ctrl+Enter to generate..." 
      rows="1"
    ></textarea>

    <!-- Bottom action bar -->
    <div class="prompt-toolbar-bottom">
      <div class="quick-actions">
        <button class="icon-btn" title="Voice Input"><Mic size="18" /></button>
        <button class="icon-btn" title="System Variables"><Braces size="18" /></button>
      </div>

      <button class="btn-generate active">
        <Sparkles size="18" class="sparkle-icon" />
        <span>Run</span>
        <kbd>Ctrl+↵</kbd>
      </button>
    </div>
  </div>
</div>
```

**Component Styling:**

```css
.prompt-box-container {
  padding: 16px 24px 24px;
  background: linear-gradient(180deg, transparent 0%, var(--bg-app) 30%);
  position: sticky;
  bottom: 0;
  z-index: 10;
}

.prompt-box {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-2xl);
  padding: 12px 18px;
  box-shadow: var(--shadow-elevation-2);
  transition: all 0.2s cubic-bezier(0.2, 0, 0, 1);
}

.prompt-box:focus-within {
  border-color: rgba(138, 180, 248, 0.6);
  box-shadow: var(--shadow-elevation-3), var(--shadow-glow);
  background: var(--bg-surface-elevated);
}

.prompt-textarea {
  width: 100%;
  min-height: 48px;
  max-height: 300px;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-family: var(--font-family-base);
  font-size: var(--font-size-body-lg);
  resize: none;
}

.btn-generate {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--primary-accent);
  color: var(--text-inverse);
  font-weight: 500;
  border: none;
  border-radius: var(--radius-pill);
  padding: 8px 18px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-generate:hover {
  background: var(--primary-accent-hover);
  box-shadow: var(--shadow-elevation-1);
}
```

---

### 3.2 Output & Chat Messages (Chat Bubbles & Output Stream)

- **Frameless feel**: Card background is only one shade higher than the main surface (`--bg-surface`).
- **Generous curvature**: `var(--radius-xl)` (24px) with subtle directional asymmetry.
- **Agent designation**: Left border indicator cleanly color-coded to the active specialized agent (`var(--agent-color)`).
- **Syntax-highlighted Codeblocks**: Dark slate containers with top bar (language badge + copy button).

```css
.message-card {
  border-radius: var(--radius-xl);
  padding: 16px 20px;
  margin-bottom: 16px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  line-height: 1.6;
}

.message-card.user {
  background: var(--bg-surface-variant);
  margin-left: 15%;
  border-bottom-right-radius: 4px;
}

.message-card.model {
  background: var(--bg-surface);
  margin-right: 5%;
  border-bottom-left-radius: 4px;
  position: relative;
}

.message-card.model::before {
  content: '';
  position: absolute;
  left: -2px;
  top: 16px;
  bottom: 16px;
  width: 3px;
  border-radius: 2px;
  background: var(--agent-color, var(--primary-accent));
}
```

---

### 3.3 Right Panel Configuration Controls

The parameters panel provides:

1. **Model Selector (Dropdown)**: Styled dropdown card with token context limit chips.
2. **Range Sliders (Temperature, Top-K, Top-P)**: Smooth custom sliders with real-time numeric indicator.
3. **Toggle Switches**: Switches for Structured Outputs (JSON Schema) and Safety thresholds.

```css
/* M3 Range Slider */
.slider-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.slider-header {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-body-md);
  color: var(--text-secondary);
}

.slider-input {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 4px;
  background: var(--border-subtle);
  border-radius: var(--radius-pill);
  outline: none;
}

.slider-input::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--primary-accent);
  cursor: pointer;
  box-shadow: 0 0 8px rgba(138, 180, 248, 0.4);
  transition: transform 0.15s ease;
}

.slider-input::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}
```

---

## 4. Icons & Micro-animations

### 4.1 Iconography (@lucide/svelte)

All interface icons are sourced from `@lucide/svelte` with consistent line weight `strokeWidth={1.75}`:

- **`Sparkles`**: Signature Gemini indicator & Run button.
- **`SlidersHorizontal`**: Parameters & config panel toggle.
- **`History` / `Clock`**: Session history list.
- **`Braces`**: JSON Schema / Structured Outputs mode.
- **`Play` / `Send`**: Prompt execution trigger.
- **`Copy` / `Check`**: Output snippet copy feedback.
- **`Bot` / `User`**: Conversation participant avatars.

### 4.2 Generation States & Animations

#### 1. Sparkles Animation (Gemini Breathing Pulse)

```css
@keyframes gemini-pulse {
  0% {
    filter: drop-shadow(0 0 2px rgba(66, 133, 244, 0.4));
    transform: scale(1) rotate(0deg);
  }
  50% {
    filter: drop-shadow(0 0 10px rgba(155, 114, 203, 0.8));
    transform: scale(1.1) rotate(6deg);
  }
  100% {
    filter: drop-shadow(0 0 2px rgba(66, 133, 244, 0.4));
    transform: scale(1) rotate(0deg);
  }
}

.generating-sparkle {
  animation: gemini-pulse 2.2s infinite ease-in-out;
  color: #8ab4f8;
}
```

#### 2. Shimmer & Skeleton Loading

```css
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton-line {
  height: 14px;
  margin-bottom: 8px;
  border-radius: var(--radius-xs);
  background: linear-gradient(
    90deg,
    var(--bg-surface-variant) 25%,
    var(--bg-surface-elevated) 50%,
    var(--bg-surface-variant) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.8s infinite ease-in-out;
}
```

#### 3. Streaming Cursor

```css
@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.streaming-cursor {
  display: inline-block;
  width: 8px;
  height: 18px;
  vertical-align: middle;
  background: var(--gemini-gradient-active);
  border-radius: 2px;
  margin-left: 4px;
  animation: cursor-blink 0.9s infinite;
}
```

---

## 5. Frontend Implementation Checklist

- [ ] All surface tokens align with Google AI Studio dark mode (`#131314` base canvas).
- [ ] Run / Generate CTA utilizes signature Gemini gradient with smooth hover expansion.
- [ ] Icons imported strictly from `@lucide/svelte` with 18-20px sizing and 1.75 stroke-width.
- [ ] Prompt Input box is floating, auto-expanding with 24px-32px radius.
- [ ] Right parameters drawer collapses into an overlay panel on viewport widths < 1200px.
- [ ] Streaming markdown output is augmented with the animated gradient cursor.
