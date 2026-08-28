# Repository Guidelines

## Project Structure & Module Organization

- `agents/` contains Google ADK agents. Each agent normally exposes `agent.py`; shared Gemini configuration lives in `agents/gemini_config.py`.
- `agents/root_agent/` routes work to specialized agents. Video Editor and Receipt Scanner also expose A2A servers in `a2a_server.py`.
- Each agent that needs evaluations should own them in `agents/<agent_name>/evaluation/`. Keep evaluator code, datasets, ADK config, manifests, baseline reports, and runner modules together there.
- `tests/` contains Python `unittest` modules. 
- `frontend/` is the Svelte/Vite UI. 
- `docs/` contains setup and evaluation guidance.

## Build, Test, and Development Commands

- `make help` — list supported workspace commands.
- `make run-all` — start A2A services, ADK web on port 8080, and the frontend.
- `npm run build --prefix frontend` — build the Svelte frontend.
- `uv run --locked python -m unittest discover tests -v` — run the Python suite.
- `make linkedin-judge-evals` / `make linkedin-evals` — current LinkedIn examples; add analogous targets as other agents gain evaluation suites.

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
intentional behavior changes.

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

## Agent Visual Identity & Iconography Standards (Mandatory)

Whenever rendering agents in UI components (catalog cards, active chat avatars, execution badges, modals, graph views, and logs), you MUST strictly use the canonical Lucide icons and colors defined below. NEVER substitute with generic sparkles or placeholder icons:

| Agent ID | Display Name | Lucide Icon | Accent Color Token | Domain & Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `root_agent` | **Main** | `Layers` | `--agent-root` (`#4285F4`) | Root Orchestrator & Multi-agent Router |
| `receipt_scanner` | **Receipt Scanner** | `Receipt` | `--agent-receipt` (`#34A853`) | Receipt OCR, Banking FX, Google Docs |
| `video_editor` | **Live Video Editor** | `Video` | `--agent-video` (`#FBBC04`) | Face Detection, 9:16 Outpainting, Omni Videos |
| `linkedin_post_generator` | **LinkedIn Planner** | `Share2` | `--agent-linkedin` (`#0A66C2`) | Speaker Announcements & Recap Posts |
| `registration_manager` | **Registrations Manager** | `Users` | `--agent-registration` (`#A142F4`) | Participant Roster Clean & Partitioning |
| `event_planner` | **Event Scheduler** | `Calendar` | `--agent-planner` (`#EA4335`) | Polish Holidays & Tech Meetup Calendars |
| `agenda_generator` | **Agenda Formatter** | `Clock` | `--agent-agenda` (`#24C1E0`) | Event Agendas & Minute-level Timelines |
| `office_secretary` | **Office Secretary** | `Mail` | `--agent-office` (`#FA7B17`) | Visitor Key Access & Room Reservation Emails |

### Iconography & Emoji Rule (Mandatory)
- **NO Raw Emoji in UI**: Never use standard/raw emoji characters (e.g. `⚙️`, `🚀`, `🧾`, `📸`, `📊`, `📑`, `💡`) in UI components, buttons, dropzones, chips, cards, dialogs, or headers.
- **Lucide Icons Exclusively**: Always use vector SVG icons from `@lucide/svelte` with semantic sizing (`14px`, `16px`, `18px`, `20px`, `24px`) and theme color tokens.

## AI Skills & Agent Workflows

Manage agent skills via [skills.sh](https://skills.sh/) (`npx skills`). Store `skills-lock.json` in the repository root instead of committing local skill markdown files for public sources. Restore installed skills using:

```bash
npx skills experimental_install
```

Recommended core skills by domain:
- **UI / Frontend**: `googlechrome/modern-web-guidance` (`https://www.skills.sh/googlechrome/modern-web-guidance/modern-web-guidance`)
- **API**: `fastapi/fastapi` (`https://www.skills.sh/fastapi/fastapi/fastapi`)
- **ADK / Agents**: `google/agents-cli` (`https://github.com/google/agents-cli#agent-skills`)

## Dependencies & Environment

- Use uv exclusively for Python dependency management. Add and remove dependencies with `uv add` and `uv remove`; resolve them with `uv lock`; install them with `uv sync`; and execute project tools with `uv run`.
- Do not use `pip`, `requirements.txt`, or `setup.py`. Keep all direct dependencies pinned in `pyproject.toml` and commit the matching `uv.lock`.
- All documentation, tests, and configurations must use relative paths (never hardcode machine-specific absolute paths or `file:///Users/...` links).

## Security & Configuration

Do not commit `.env`, credentials, tokens, generated `.adk/` history, or
participant/output files. Copy `.env.example` for local configuration and use
the configured Gemini backend rather than embedding keys in code.
