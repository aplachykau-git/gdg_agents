@AGENTS.md

# Notes for Claude Code

`AGENTS.md` (imported above) holds the rules for every coding agent working in this repo;
change rules there, not here. Only Claude-specific notes belong in this file.

- Code, comments, docs, prompts and UI text are in English, even when the conversation is not.
- Before finishing a change, run `uv run --locked ruff check agents tests`,
  `uv run --locked python -m unittest discover tests` and, for frontend changes,
  `npm test --prefix frontend` and `npm run build --prefix frontend`.
- For a visible frontend change, look at it (dark, light, ~400 px wide), not only at the build.
