"""Evaluation-only video-editor agent.

Uses the real instruction and the real tools, but in offline mode: scenarios come from the
deterministic fallback set and renders return the bundled sample video. Only the chat model
is called, so the conversation contract can be evaluated cheaply and repeatedly.
"""

import os

os.environ.setdefault("VIDEO_EDITOR_OFFLINE", "true")

from google.adk import Agent  # noqa: E402

from agents.video_editor.agent import INSTRUCTION, video_editor_agent  # noqa: E402
from agents.video_editor.tools.card_tools import ALL_TOOLS  # noqa: E402

EVALUATION_MODEL = os.getenv("VIDEO_EDITOR_EVAL_MODEL", str(video_editor_agent.model))

root_agent = Agent(
    model=EVALUATION_MODEL,
    name="video_editor",
    description="Evaluation-only video editor (offline rendering).",
    instruction=INSTRUCTION,
    tools=list(ALL_TOOLS),
    generate_content_config=video_editor_agent.generate_content_config,
)
