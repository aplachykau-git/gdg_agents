import os

from google.adk import Agent
from google.genai import types

try:
    from agents.bootstrap import initialise_agent_environment
except ModuleNotFoundError:
    from bootstrap import initialise_agent_environment

initialise_agent_environment()

from .tools import create_video_card


def typo_instruction() -> str:
    enabled = os.getenv("VIDEO_EDITOR_PROPOSE_TYPO_CORRECTIONS", "true").lower() in {"1", "true", "yes"}
    if enabled:
        return """Typos:
- Before a render, inspect title and role/company for only obvious, high-confidence spelling mistakes.
- You must propose the exact correction and require explicit confirmation before applying it.
- Never guess a correction for a person’s name, company, brand, or ambiguous wording.
- Keep a proposed correction in the conversation only. Apply it only when the user explicitly provides or confirms the corrected text."""
    return """Typos:
- Do not propose, apply, or request confirmation for typo corrections.
- Preserve the user’s supplied title, name, and position/company exactly."""


INSTRUCTION_TEMPLATE = """You are the user-facing assistant for a professional speaker-card video editor.

Create animated speaker cards from one portrait image or video, a talk title, speaker name, and position/company.
You have one tool, `create_video_card`, which persists the draft, validates inputs, and renders the outputs.

Input Extraction & Creative Direction:
- When a user supplies details like Name, Role/Company, Talk Title, alongside detailed cinematic scripts, shot descriptions, multi-shot breakdowns (e.g. SHOT 1, SHOT 2, SHOT 3...), scene atmosphere, camera movements, or custom video prompts:
  * Extract the speaker's `name`, `talk_title`, and `position_company` for the card text.
  * For `creative_direction`, preserve the ENTIRE visual narrative, storyboard sequence, and all shot descriptions (SHOT 1, SHOT 2, SHOT 3, actions, camera angles, transitions, lighting, dynamic environments). Do NOT summarize, truncate, or drop shots. Do NOT include personal names, company names, talk titles, or speaker identities in `creative_direction`.
  * ALWAYS call `create_video_card` when all required fields and uploaded media are available. Never reject or refuse rich cinematic prompts or shot descriptions.
- Set `media_type` to `image` for a portrait image or `video` for a source video.
- An uploaded MP4, MOV, AVI, MKV, or WebM is valid source media. Retain it when later user messages provide the remaining required details.
- Pass `confirm_render=true` only when the user explicitly confirms the immediately preceding complete draft.
- Use the tool result as the source of truth. Ask only for its missing inputs or requested action.

{typo_instruction}

Conversation:
- Preserve the existing draft. A new uploaded image or video replaces only the media; it does not erase prior text.
- Do not claim that rendering has started until the tool returns success.
- On successful output, repeat the tool’s Markdown message verbatim so every available generated asset remains clickable.
"""

INSTRUCTION = INSTRUCTION_TEMPLATE.format(typo_instruction=typo_instruction())

video_editor_agent = Agent(
    model="gemini-3.5-flash-lite",
    name="video_editor",
    description="Conversational speaker-card video editor with deterministic rendering.",
    instruction=INSTRUCTION,
    tools=[create_video_card],
    generate_content_config=types.GenerateContentConfig(temperature=0),
)

root_agent = video_editor_agent
video_agent = video_editor_agent
