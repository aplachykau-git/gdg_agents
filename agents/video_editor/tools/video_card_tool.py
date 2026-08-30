from __future__ import annotations

import os
from typing import Annotated, Literal, Sequence

from google.adk.tools import ToolContext
from pydantic import Field

from ..video_card_service import (
    _latest_user_upload,
    draft_fingerprint,
    merge_draft,
    missing_draft_fields,
    render_video_card,
)
from ..workflow_models import RenderedAsset, ValidationFailure, VideoCardToolResult, VideoEditorDraft

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
    confirm_render: bool = False,
    tool_context: ToolContext | None = None,
) -> dict:
    """Create a speaker-card video from required title, name, position/company, and uploaded image or video media.

    `talk_title`, `name`, `position_company`, and `media_type` are required on every call.
    The declared `media_type` must match the latest uploaded attachment or the media already held in the current draft.
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
    draft = merge_draft(
        draft,
        title=talk_title,
        name=name,
        position_company=position_company,
        creative_direction=creative_direction,
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
