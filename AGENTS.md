# Repository Guidelines

## Project Structure & Module Organization

- `agents/` contains Google ADK agents. Each agent normally exposes `agent.py`; shared Gemini configuration lives in `agents/gemini_config.py`.
- `agents/root_agent/` routes work to specialized agents. Video Editor and Receipt Scanner also expose A2A servers in `a2a_server.py`.
- `agents/common/` is the shared core: `ui_payloads.py` (card contract), `event_profile.py` + `event_profile_tools.py` (event details and social profiles), `event_series.py`, `runtime.py` (sessions), `a2a_auth.py`.
- `agents/mcp_server.py` exposes the heavy tools over MCP (experiment, keep it).
- Each agent that needs evaluations should own them in `agents/<agent_name>/evaluation/`. Keep evaluator code, datasets, ADK config, manifests, baseline reports, and runner modules together there.
- `tests/` contains Python `unittest` modules. 
- `frontend/` is the Svelte/Vite UI. 
- `docs/` contains setup and evaluation guidance. `docs/architecture.mmd` is the single source of the architecture diagram (`make diagrams` renders `docs/assets/`; the README embeds the same Mermaid).

## Build, Test, and Development Commands

- `make help` — list supported workspace commands.
- `make run-all` — start A2A services, ADK web on port 8180, and the frontend.
- `npm run build --prefix frontend` — build the Svelte frontend.
- `uv run --locked python -m unittest discover tests -v` — run the Python suite.
- `make linkedin-judge-evals` / `make linkedin-evals` — current LinkedIn examples; add analogous targets as other agents gain evaluation suites.
- `npm test --prefix frontend` — frontend unit tests (`node --test`, no extra deps).
- `make diagrams` — re-render the architecture diagram after editing `docs/architecture.mmd`.

Use `uv sync --locked` before running Python commands. Use `make tools` to inspect resolved commands.

## Coding Style & Naming Conventions

Use Python 3.12-compatible code, four-space indentation, type hints where
useful, and double-quoted strings. Ruff enforces import ordering and core
Python style:

```bash
uv run --locked ruff check agents tests
```

Name agents and packages with lowercase snake_case (for example,
`linkedin_post_generator`). Keep agent entry points named `agent.py`; use
`test_*.py` for tests and descriptive `*_eval_set.json` names for eval data.

## Testing & Evaluation Guidelines

Add deterministic unit coverage for parsers, validation, and edge cases.
Live agent/judge runs require configured Gemini or Vertex credentials and
network access. For each evaluated agent, keep its assets under
`agents/<agent_name>/evaluation/`; use a held-out judge set separately from
few-shot training examples. Never insert held-out examples into the training
set. When changing an agent prompt, model, rubric, fixture, or threshold,
update that agent's manifest and create an approved baseline only for
intentional behavior changes. The receipt scanner manifest pins the prompt with
`production_prompt_sha256`: recompute it (sha256 of `INSTRUCTION`) when the prompt changes,
and give evaluation-only agents the same tools as production (stub them).

The video editor cannot render real Omni video on every test run. Use
`VIDEO_EDITOR_OFFLINE=true` for chat and UI work, mock `render_composer` in unit tests, and
test ffmpeg post-processing (cover frame, GIF, 4K) on tiny synthetic clips
(`tests/test_video_cover_frame.py`). Run a real HyperFrames render only for template changes.

## Working Agreements

- The studio runs mostly locally. Do not add automatic cloud deploys or paid always-on
  services (e.g. Cloud SQL) without asking; cloud pieces stay optional.
- No emoji in tool status labels, chips, buttons or card headers (see Iconography below).
- Settings hold only app-wide things (chapter name, video rendering, Google Drive). Event
  details and social profiles are set in the chat through `update_event_profile` and its card.
- Never put tokens or secrets into agent instructions or delegation text; pass them in session state.

## Commits & Pull Requests

Use Conventional Commits with an imperative header:

```text
<type>(optional-scope): short summary
```

Use types such as `feat`, `fix`, `test`, `docs`, `refactor`, `chore`, and
`style`; for example, `test(linkedin): add recap eval coverage`. Keep the
header concise and focused on one change. A commit body/description is
optional; add one only when context, rationale, or breaking-change notes are
needed.

Keep pull requests focused. Include a short summary, tests/evals run, linked
issue when applicable, and screenshots for visible frontend changes. Call out
changes to prompts, manifests, baselines, or held-out eval data explicitly.

## Adding or Changing an Agent (Checklist)

An agent is wired in several places; missing one is how agents end up half-integrated.

1. `agents/<agent_name>/agent.py` (+ `tools.py`), registered in `agents/root_agent/agent.py`
   `sub_agents` and in the root instruction's routing rules.
2. Frontend: `frontend/src/lib/config.js` (`DEFAULT_APPS` and `AGENT_CAPABILITIES_CATALOG`),
   `frontend/src/App.svelte` (agent list + icon map), `frontend/src/lib/agents.js` (theme,
   name, description, starter prompts, `transfer_to_<agent>` and per-tool status labels),
   `frontend/src/lib/AgentGraph.svelte` (`AGENTS_META`, tools list), `frontend/src/app.css`
   (`--agent-<x>` / `--bg-<x>`, with a light-theme override if the colour is light).
3. Docs: the table below, `docs/design.md` §1.4, `docs/architecture.mmd` (+ `make diagrams`
   and the README copy), `docs/SOLUTION_ARCHITECTURE.md` inventory.
4. Tests: `tests/test_docs_consistency.py` fails when an agent from `sub_agents` is missing
   in any of the places above.

## Result Cards (UI Payload Contract)

- Agents never make the UI parse prose. A tool returns `{"ui": {"type": ...}}` (or a text
  agent attaches it via `text_ui_callback`); builders live in `agents/common/ui_payloads.py`,
  adapters in `frontend/src/lib/ui/payloads.js`, routing in `StructuredCard.svelte`.
- One event may carry several payloads (parallel tool calls); `ChatMessage` renders all.
- New cards use `frontend/src/lib/ui/ResultCard.svelte` (header with icon, title, subtitle,
  status; body; actions/tools footer) and its shared classes (`rc-btn`, `rc-chip`, `rc-facts`,
  `rc-label`, `rc-muted`). Check dark, light and a 400 px wide viewport.
- Interactive cards reply through `onSend(text, extraState)`: the state goes as `state_delta`,
  the text tells the agent what happened (e.g. "Saved the event details.").
- Pairs that must stay in sync (tests check them): `DEFAULT_SEQUENCE` in
  `agents/linkedin_post_generator/countdown.py` and `DEFAULT_COUNTDOWN_PLAN` in `config.js`;
  `NETWORKS` in `agents/common/event_profile.py` and `SOCIAL_NETWORKS` in `config.js`.

## Agent Visual Identity & Iconography Standards (Mandatory)

Whenever rendering agents in UI components (catalog cards, active chat avatars, execution badges, modals, graph views, and logs), you MUST strictly use the canonical Lucide icons and colors defined below. NEVER substitute with generic sparkles or placeholder icons:

| Agent ID | Display Name | Lucide Icon | Accent Color Token (dark / light) | Domain & Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `root_agent` | **Main** | `Layers` | `--agent-root` (`#38bdf8`) | Root Orchestrator & Multi-agent Router |
| `receipt_scanner` | **Receipt Scanner** | `Receipt` | `--agent-receipt` (`#2dd4bf`) | Receipt OCR, recognised-receipts card, Banking FX, Google Docs |
| `video_editor` | **Live Video Editor** | `Video` | `--agent-video` (`#a855f7`) | Face Detection, 9:16 Outpainting, Omni Videos, cover frame |
| `linkedin_post_generator` | **Social Planner** | `Share2` | `--agent-linkedin` (`#60a5fa`) | Speaker Announcements, Recaps, Countdown Plans for all networks, Event Profile |
| `registration_manager` | **Registrations Manager** | `Users` | `--agent-registration` (`#fbbf24`) | Participant Roster Clean & Partitioning |
| `event_planner` | **Event Scheduler** | `Calendar` | `--agent-planner` (`#f43f5e`) | Polish Holidays & Tech Meetup Calendars |
| `agenda_generator` | **Agenda Formatter** | `Clock` | `--agent-agenda` (`#34d399`) | Event Agendas & Minute-level Timelines |
| `office_secretary` | **Office Secretary** | `Mail` | `--agent-office` (`#ec4899`) | Visitor Key Access & Room Reservation Emails |
| `qr_code_generator` | **QR Code Generator** | `QrCode` | `--agent-qr` (`#a3e635` / `#4d7c0f`) | Rounded QR Codes, flat SVG + PNG |

The tokens in `frontend/src/app.css` are the source of truth; the hex values above mirror them.
`AgentGraph.svelte` still hard-codes Google brand hex values per node; move them to the tokens
when that view is next changed.

### Iconography & Emoji Rule (Mandatory)
- **NO Raw Emoji in UI**: Never use standard/raw emoji characters (e.g. `⚙️`, `🚀`, `🧾`, `📸`, `📊`, `📑`, `💡`) in UI components, buttons, dropzones, chips, cards, dialogs, or headers.
- **Lucide Icons Exclusively**: Always use vector SVG icons from `@lucide/svelte` with semantic sizing (`14px`, `16px`, `18px`, `20px`, `24px`) and theme color tokens.

## AI Skills & Agent Workflows

Manage agent skills via [skills.sh](https://skills.sh/) (`npx skills`). Store `skills-lock.json` in the repository root instead of committing local skill markdown files for public sources. Restore installed skills using:

```bash
npx skills experimental_install
```

Recommended core skills by domain:
- **UI / Frontend & Svelte 5**: `googlechrome/modern-web-guidance`, `sveltejs/ai-tools` (`svelte-core-bestpractices`, `svelte-code-writer`), `ejirocodes/agent-skills` (`svelte5-best-practices`), `sveltekit`
- **Node.js**: `wshobson/agents` (`nodejs-backend-patterns`), `sickn33/agentic-awesome-skills` (`nodejs-best-practices`), `mcollina/skills` (`nodejs-core`)
- **API**: `fastapi/fastapi` (`https://www.skills.sh/fastapi/fastapi/fastapi`)
- **ADK / Agents**: `google/agents-cli` (`https://github.com/google/agents-cli#agent-skills`)
- **Video / HyperFrames**: `heygen-com/hyperframes` (`hyperframes`, `hyperframes-core`, `hyperframes-animation`, `hyperframes-cli`, `media-use`)

## Dependencies & Environment

- Use uv exclusively for Python dependency management. Add and remove dependencies with `uv add` and `uv remove`; resolve them with `uv lock`; install them with `uv sync`; and execute project tools with `uv run`.
- Do not use `pip`, `requirements.txt`, or `setup.py`. Keep all direct dependencies pinned in `pyproject.toml` and commit the matching `uv.lock`.
- All documentation, tests, and configurations must use relative paths (never hardcode machine-specific absolute paths or `file:///Users/...` links).

## Security & Configuration

Do not commit `.env`, credentials, tokens, generated `.adk/` history, or
participant/output files. Copy `.env.example` for local configuration and use
the configured Gemini backend rather than embedding keys in code.
