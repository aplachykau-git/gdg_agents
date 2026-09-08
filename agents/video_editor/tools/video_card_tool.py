from __future__ import annotations

import os
from typing import Annotated, Literal, Sequence

from google.adk.tools import ToolContext
from pydantic import Field

from agents.gemini_config import get_gemini_client

from ..prompt_director import format_scenarios_markdown, generate_creative_scenarios
from ..video_card_service import (
    _latest_user_upload,
    draft_fingerprint,
    merge_draft,
    missing_draft_fields,
    render_video_card,
)
from ..workflow_models import RenderedAsset, ValidationFailure, VideoCardToolResult, VideoEditorDraft
from . import media_tools

DRAFT_STATE_KEY = "video_editor_draft"
COMPLETED_MEDIA_STATE_KEY = "video_editor_completed_media"


def confirmation_required() -> bool:
    return os.getenv("VIDEO_EDITOR_REQUIRE_CONFIRMATION", "false").lower() in {"1", "true", "yes"}


def _validate_required_inputs(
    talk_title: str,
    name: str,
    position_company: str,
    media_type: Literal["image", "video"],
    media: object,
) -> VideoCardToolResult | None:
    missing = [
        label
        for label, value in (
            ("talk title", talk_title),
            ("speaker name", name),
            ("position and company", position_company),
        )
        if not value.strip()
    ]
    if missing:
        return VideoCardToolResult(
            status="error",
            code="missing_input",
            message=f"Please provide: {', '.join(missing)}.",
            requested_action="provide_details",
            missing_fields=missing,
        )
    if media is None:
        return VideoCardToolResult(
            status="error",
            code="missing_media",
            message=f"Please upload a portrait {media_type}.",
            requested_action="replace_media",
            missing_fields=[f"portrait {media_type}"],
        )
    mime_type = getattr(media, "mime_type", "")
    if not mime_type.startswith(f"{media_type}/"):
        return VideoCardToolResult(
            status="error",
            code="media_type_mismatch",
            message=f"The uploaded media is not an {media_type}. Please upload an {media_type}.",
            requested_action="replace_media",
        )
    return None


def _load_draft(tool_context: ToolContext) -> VideoEditorDraft:
    return VideoEditorDraft.model_validate(tool_context.state.get(DRAFT_STATE_KEY, {}))


def _save_draft(tool_context: ToolContext, draft: VideoEditorDraft) -> None:
    tool_context.state[DRAFT_STATE_KEY] = draft.model_dump()


def _draft_summary(draft: VideoEditorDraft) -> str:
    media = "uploaded media" if draft.media else "no media uploaded"
    direction = draft.creative_direction or "default professional direction"
    return (
        "Please confirm this video card: "
        f"title “{draft.title}”; speaker “{draft.name}”; role/company “{draft.position_company}”; "
        f"{media}; creative direction “{direction}”. Reply yes to render it."
    )


def _failure_result(failure: ValidationFailure, draft: VideoEditorDraft) -> VideoCardToolResult:
    action = "replace_media" if failure.requested_action == "replace_media" else "correct_text"
    return VideoCardToolResult(
        status="error",
        code=failure.code,
        message=failure.message,
        retryable=failure.retryable,
        requested_action=action,
        draft=draft,
    )


def format_render_success_message(assets: Sequence[RenderedAsset]) -> str:
    lines = ["Generation complete."]
    for asset in assets:
        if asset.availability == "available" and asset.url:
            lines.append(f"- [{asset.label}]({asset.url})")
        else:
            lines.append(f"- {asset.label}: {asset.unavailable_reason or 'Download unavailable.'}")
    return "\n".join(lines)


def should_propose_scenarios(
    tool_context: ToolContext,
    media_type: str,
    creative_direction: str | None,
    selected_scenario_id: str | None,
    regenerate_scenarios: bool,
    has_suggested_scenarios: bool = False,
) -> bool:
    if media_type != "image":
        return False
    if regenerate_scenarios:
        return True
    if selected_scenario_id:
        return False
    # If scenarios have already been proposed, and user provides custom prompt without an ID:
    if has_suggested_scenarios and creative_direction:
        return False
    # If user explicitly provided their own rich multi-shot storyboard (e.g. SHOT 1, SHOT 2):
    if creative_direction and ("shot 1" in creative_direction.lower() or "shot 2" in creative_direction.lower()):
        return False

    return True


async def create_video_card(
    talk_title: Annotated[str, Field(description="Required talk title displayed on the speaker card.")],
    name: Annotated[str, Field(description="Required speaker name displayed on the speaker card.")],
    position_company: Annotated[
        str,
        Field(description="Required combined speaker position and company displayed on the speaker card."),
    ],
    media_type: Annotated[
        Literal["image", "video"],
        Field(
            description="Required type of the uploaded source media: `image` for a portrait image or `video` for a source video."
        ),
    ],
    creative_direction: str | None = None,
    selected_scenario_id: str | None = None,
    speaker_bio: str | None = None,
    regenerate_scenarios: bool = False,
    confirm_render: bool = False,
    tool_context: ToolContext | None = None,
) -> dict:
    """Create a speaker-card video from required title, name, position/company, and uploaded image or video media.

    `talk_title`, `name`, `position_company`, and `media_type` are required on every call.
    When video generation is enabled, offers creative 5-shot x 2-second cinematic scenarios before rendering.
    """
    if tool_context is None:
        raise ValueError("tool_context is required.")

    draft = _load_draft(tool_context)
    current_upload = _latest_user_upload(tool_context)
    completed_media = tool_context.state.get(COMPLETED_MEDIA_STATE_KEY)
    if current_upload and current_upload.model_dump() == completed_media:
        current_upload = None
    if current_upload == draft.media:
        current_upload = None
    input_failure = _validate_required_inputs(
        talk_title,
        name,
        position_company,
        media_type,
        current_upload or draft.media,
    )
    if input_failure:
        return input_failure.model_dump()

    # Handle scenario selection from existing scenarios if provided
    resolved_direction = creative_direction
    matched_scenario_id = selected_scenario_id
    if selected_scenario_id and draft.suggested_scenarios:
        for sc in draft.suggested_scenarios:
            if sc.id.lower() == selected_scenario_id.lower() or selected_scenario_id.lower() in sc.title.lower():
                matched_scenario_id = sc.id
                if not resolved_direction:
                    resolved_direction = sc.omni_prompt
                break

    draft = merge_draft(
        draft,
        title=talk_title,
        name=name,
        position_company=position_company,
        creative_direction=resolved_direction,
        selected_scenario_id=matched_scenario_id,
        media=current_upload,
    )

    missing_fields = missing_draft_fields(draft)
    if missing_fields:
        _save_draft(tool_context, draft)
        return VideoCardToolResult(
            status="error",
            code="missing_input",
            message=f"Please provide: {', '.join(missing_fields)}.",
            requested_action="provide_details",
            missing_fields=missing_fields,
            draft=draft,
        ).model_dump()

    # If video generation is enabled and no scenario chosen yet, propose 5x2s cinematic scenarios
    has_existing = bool(draft.suggested_scenarios)
    if should_propose_scenarios(
        tool_context,
        media_type,
        draft.creative_direction,
        draft.selected_scenario_id,
        regenerate_scenarios,
        has_suggested_scenarios=has_existing,
    ):
        scenarios = generate_creative_scenarios(
            talk_title=draft.title or talk_title,
            speaker_name=draft.name or name,
            position_company=draft.position_company or position_company,
            speaker_bio=speaker_bio,
        )

        draft = merge_draft(
            draft,
            title=talk_title,
            name=name,
            position_company=position_company,
            creative_direction=None,
            selected_scenario_id=None,
            media=current_upload,
            suggested_scenarios=scenarios,
        )
        _save_draft(tool_context, draft)
        msg = (
            f"{format_scenarios_markdown(scenarios)}\n\n"
            "🎬 **Choose a Video Concept or Refine the Prompt:**\n"
            "Please select which scenario you would like to render (e.g. **Option 1**, **Option 2**, or **Option 3**), "
            "or modify the prompt shots before we render."
        )
        return VideoCardToolResult(
            status="awaiting_confirmation",
            message=msg,
            requested_action="select_scenario",
            scenarios=scenarios,
            draft=draft,
        ).model_dump()

    # Block rendering if scenarios were suggested but none chosen and no creative direction set
    if draft.suggested_scenarios and not draft.selected_scenario_id and not draft.creative_direction:
        _save_draft(tool_context, draft)
        return VideoCardToolResult(
            status="awaiting_confirmation",
            message=(
                "Please select one of the suggested creative scenarios (e.g. Option 1, Option 2, Option 3) "
                "or customize the prompt before rendering."
            ),
            requested_action="select_scenario",
            scenarios=draft.suggested_scenarios,
            draft=draft,
        ).model_dump()

    fingerprint = draft_fingerprint(draft)
    if confirmation_required() and draft.confirmed_fingerprint != fingerprint:
        if not confirm_render:
            _save_draft(tool_context, draft)
            return VideoCardToolResult(
                status="awaiting_confirmation",
                message=_draft_summary(draft),
                requested_action="confirm_render",
                draft=draft,
            ).model_dump()
        draft.confirmed_fingerprint = fingerprint

    rendered = await render_video_card(draft, tool_context)
    if isinstance(rendered, ValidationFailure):
        _save_draft(tool_context, draft)
        return _failure_result(rendered, draft).model_dump()

    tool_context.state[COMPLETED_MEDIA_STATE_KEY] = draft.media.model_dump() if draft.media else {}
    tool_context.state[DRAFT_STATE_KEY] = {}
    return VideoCardToolResult(
        status="success",
        message=format_render_success_message(rendered.assets),
        assets=rendered.assets,
    ).model_dump()
