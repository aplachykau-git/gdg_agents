"""Evaluation-only video-editor agent with a deterministic render stub."""

import os
from typing import Annotated, Literal

from google.adk import Agent
from google.adk.tools import ToolContext
from pydantic import Field

from agents.video_editor.agent import INSTRUCTION, video_editor_agent

EVALUATION_MODEL = os.getenv("VIDEO_EDITOR_EVAL_MODEL", str(video_editor_agent.model))


def create_video_card(
    talk_title: Annotated[str, Field(description="Required talk title.")],
    name: Annotated[str, Field(description="Required speaker name.")],
    position_company: Annotated[str, Field(description="Required combined speaker position and company text.")],
    media_type: Annotated[
        Literal["image", "video"],
        Field(description="Required type of the uploaded source media."),
    ],
    creative_direction: str | None = None,
    confirm_render: bool = False,
    tool_context: ToolContext | None = None,
) -> dict:
    """Capture a production-shaped video-card request without rendering media."""
    del tool_context
    missing = [
        label
        for label, value in (
            ("talk title", talk_title),
            ("speaker name", name),
            ("position and company", position_company),
            ("media type", media_type),
        )
        if not value
    ]
    if missing:
        return {
            "status": "error",
            "code": "missing_input",
            "message": f"Please provide: {', '.join(missing)} and upload a portrait image or video.",
            "missing_fields": missing + ["portrait image or video"],
        }
    if os.getenv("VIDEO_EDITOR_REQUIRE_CONFIRMATION", "false").lower() in {"1", "true", "yes"} and not confirm_render:
        return {
            "status": "awaiting_confirmation",
            "message": "Please confirm the complete video-card draft before rendering.",
            "requested_action": "confirm_render",
        }
    return {
        "status": "success",
        "message": "Evaluation render completed.",
        "assets": [
            {"label": "Video", "url": "https://example.invalid/video-editor-eval.mp4"},
            {"label": "Poster", "url": "https://example.invalid/video-editor-eval.png"},
        ],
        "creative_direction": creative_direction or "",
    }


root_agent = Agent(
    model=EVALUATION_MODEL,
    name="video_editor",
    description="Evaluation-only video editor.",
    instruction=INSTRUCTION.replace(str(video_editor_agent.model), EVALUATION_MODEL),
    tools=[create_video_card],
)
