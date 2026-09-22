from __future__ import annotations

import os
import re
from typing import Annotated, Literal, Sequence

from google.adk.tools import ToolContext
from pydantic import Field

from agents.gemini_config import get_gemini_client

from ..prompt_director import format_scenarios_markdown, format_timed_omni_prompt, generate_creative_scenarios
from ..video_card_service import (
    _latest_user_upload,
    draft_fingerprint,
    merge_draft,
    missing_draft_fields,
    render_video_card,
)
from ..workflow_models import CreativeScenario, RenderedAsset, ValidationFailure, VideoCardToolResult, VideoEditorDraft
from . import media_tools

DRAFT_STATE_KEY = "video_editor_draft"
COMPLETED_MEDIA_STATE_KEY = "video_editor_completed_media"
LAST_RENDERED_DRAFT_KEY = "video_editor_last_rendered_draft"


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


def _load_draft(tool_context: ToolContext, allow_fallback: bool = False) -> VideoEditorDraft:
    raw = tool_context.state.get(DRAFT_STATE_KEY)
    if not raw or not isinstance(raw, dict) or not raw.get("name"):
        if allow_fallback:
            fallback = tool_context.state.get(LAST_RENDERED_DRAFT_KEY, {})
            if isinstance(fallback, dict) and fallback.get("name"):
                raw = fallback
        else:
            raw = {}
    return VideoEditorDraft.model_validate(raw or {})


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
    if failure.requested_action in ("replace_media", "retry", "correct_text"):
        action = failure.requested_action
    elif failure.requested_action == "retry_render":
        action = "retry"
    elif failure.code in (
        "media_not_found",
        "unsupported_media",
        "invalid_image",
        "invalid_video",
        "face_not_detected",
    ):
        action = "replace_media"
    else:
        action = "correct_text"
    return VideoCardToolResult(
        status="error",
        code=failure.code,
        message=failure.message,
        retryable=failure.retryable,
        requested_action=action,
        draft=draft,
    )


def format_render_success_message(assets: Sequence[RenderedAsset], notice: str = "") -> str:
    lines = []
    if notice and isinstance(notice, str):
        lines.append(notice)
        lines.append("")
    lines.append("Generation complete.")
    for asset in assets:
        if asset.availability == "available" and asset.url:
            lines.append(f"- [{asset.label}]({asset.url})")
        else:
            lines.append(f"- {asset.label}: {asset.unavailable_reason or 'Download unavailable.'}")
    return "\n".join(lines)


REOPEN_CARD_KEYWORDS = (
    "reopen",
    "повторить карточку",
    "повтори карточку",
    "открой карточку",
    "открой заново карточку",
    "переоткрой карточку",
    "отредактировать карточку",
    "редактировать карточку",
    "edit and reopen",
    "edit & reopen",
    "show card",
    "покажи карточку",
    "верни карточку",
    "покажи варианты",
    "показать варианты",
)


def is_reopen_request(creative_direction: str | None = None, reopen_existing_card: bool = False) -> bool:
    if reopen_existing_card:
        return True
    if not creative_direction:
        return False
    lower = creative_direction.strip().lower()
    return any(kw in lower for kw in REOPEN_CARD_KEYWORDS)


def should_propose_scenarios(
    tool_context: ToolContext,
    media_type: str,
    creative_direction: str | None,
    selected_scenario_id: str | None,
    regenerate_scenarios: bool,
    has_suggested_scenarios: bool = False,
    confirm_render: bool = False,
) -> bool:
    if media_type != "image":
        return False
    if confirm_render:
        return False
    if regenerate_scenarios:
        return True
    if selected_scenario_id:
        return False
    if has_suggested_scenarios:
        return False
    # If user explicitly provided their own rich multi-shot storyboard (e.g. SHOT 1, SHOT 2):
    if creative_direction and ("shot 1" in creative_direction.lower() or "shot 2" in creative_direction.lower()):
        return False

    return True


def resolve_selected_scenario_prompt(
    scenarios: Sequence[CreativeScenario],
    selected_scenario_id: str | None = None,
    creative_direction: str | None = None,
) -> tuple[CreativeScenario | None, str | None, str | None]:
    """Resolves a chosen scenario or style from suggested scenarios.

    Returns:
        (matched_scenario, matched_scenario_or_style_id, resolved_prompt)
    """
    if not scenarios:
        return None, selected_scenario_id, creative_direction

    matched_sc: CreativeScenario | None = None
    matched_style: object | None = None
    matched_id: str | None = selected_scenario_id
    resolved_prompt = creative_direction

    if selected_scenario_id:
        sel_clean = selected_scenario_id.strip()
        sel_lower = sel_clean.lower()

        # 1. Option number matching: e.g. "option 2", "вариант 3", "scenario 1", "5", "option_2"
        opt_match = re.search(r"(?:option|вариант|сценарий|scenario)[_\s]*(\d+)", sel_lower) or re.match(
            r"^(\d+)$", sel_lower
        )
        if opt_match:
            idx = int(opt_match.group(1)) - 1
            if 0 <= idx < len(scenarios):
                matched_sc = scenarios[idx]
                matched_id = matched_sc.id

        # 2. Exact match on scenario ID or style ID
        if not matched_sc:
            for sc in scenarios:
                if sc.id.lower() == sel_lower:
                    matched_sc = sc
                    matched_id = sc.id
                    break
                for st in getattr(sc, "styles", []) or []:
                    if getattr(st, "id", "").lower() == sel_lower:
                        matched_sc = sc
                        matched_style = st
                        matched_id = st.id
                        break
                if matched_sc:
                    break

        # 3. Prefix or substring match (e.g. style_5_fantasy_genre_art_movement_style_1 starts with style_5_fantasy_genre_art_movement)
        if not matched_sc:
            for sc in scenarios:
                sc_id_lower = sc.id.lower()
                if sel_lower.startswith(sc_id_lower) or sc_id_lower.startswith(sel_lower):
                    matched_sc = sc
                    matched_id = sc.id
                    for st in getattr(sc, "styles", []) or []:
                        st_id_lower = getattr(st, "id", "").lower()
                        if st_id_lower == sel_lower or sel_lower.endswith(st_id_lower.split("_")[-1]):
                            matched_style = st
                            matched_id = st.id
                            break
                    break
                if sel_lower in sc.title.lower() or sc.title.lower() in sel_lower:
                    matched_sc = sc
                    matched_id = sc.id
                    break
                for st in getattr(sc, "styles", []) or []:
                    st_name = getattr(st, "name", "").lower()
                    if st_name and (st_name in sel_lower or sel_lower in st_name):
                        matched_sc = sc
                        matched_style = st
                        matched_id = getattr(st, "id", sc.id)
                        break
                if matched_sc:
                    break

    elif creative_direction:
        cd_lower = creative_direction.lower()
        for sc in scenarios:
            if sc.title.lower() in cd_lower or sc.id.lower() in cd_lower:
                matched_sc = sc
                matched_id = sc.id
                for st in getattr(sc, "styles", []) or []:
                    st_name = getattr(st, "name", "").lower()
                    st_id = getattr(st, "id", "").lower()
                    if (st_name and st_name in cd_lower) or (st_id and st_id in cd_lower):
                        matched_style = st
                        matched_id = getattr(st, "id", sc.id)
                        break
                break

    if matched_sc:
        has_timings = bool(
            resolved_prompt and any(m in resolved_prompt.lower() for m in ("00:00", "0-2s", "shot 1", "shot 2"))
        )
        if not has_timings:
            if matched_style and getattr(matched_style, "omni_prompt", None):
                sc_prompt = matched_style.omni_prompt
                shots = getattr(matched_style, "shots", None) or matched_sc.shots
                genre = getattr(matched_style, "genre", None) or matched_sc.genre
            else:
                sc_prompt = matched_sc.omni_prompt
                shots = matched_sc.shots
                genre = matched_sc.genre

            if shots and not any(m in sc_prompt.lower() for m in ("00:00", "0-2s", "shot 1")):
                sc_prompt = format_timed_omni_prompt(shots, genre, sc_prompt)
            resolved_prompt = sc_prompt

    return matched_sc, matched_id, resolved_prompt


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
    creative_guidance: str | None = None,
    regenerate_scenarios: bool = False,
    reopen_existing_card: bool = False,
    confirm_render: bool = False,
    tool_context: ToolContext | None = None,
) -> dict:
    """Create a speaker-card video from required title, name, position/company, and uploaded image or video media.

    `talk_title`, `name`, `position_company`, and `media_type` are required on every call.
    When video generation is enabled, offers creative 5-shot x 2-second cinematic scenarios before rendering.
    """
    if tool_context is None:
        raise ValueError("tool_context is required.")

    # Check if this is a request to reopen / edit / repeat the existing card
    is_reopen = is_reopen_request(creative_direction, reopen_existing_card)
    draft = _load_draft(tool_context, allow_fallback=is_reopen)
    if name and draft.name and name.strip().lower() != draft.name.strip().lower():
        draft = VideoEditorDraft()
    elif talk_title and draft.title and talk_title.strip().lower() != draft.title.strip().lower():
        if name and draft.name and name.strip().lower() != draft.name.strip().lower():
            draft = VideoEditorDraft()

    current_upload = _latest_user_upload(tool_context)
    completed_media = tool_context.state.get(COMPLETED_MEDIA_STATE_KEY)
    if current_upload and current_upload.model_dump() == completed_media:
        current_upload = None
    if current_upload == draft.media:
        current_upload = None

    # Reconcile media_type with active upload if present
    active_media = current_upload or draft.media
    if active_media and getattr(active_media, "mime_type", None):
        mime = active_media.mime_type
        if mime.startswith("image/"):
            media_type = "image"
        elif mime.startswith("video/"):
            media_type = "video"

    if is_reopen:
        creative_direction = None
        selected_scenario_id = None
        confirm_render = False

    effective_title = (talk_title or "").strip() or (draft.title or "").strip()
    effective_name = (name or "").strip() or (draft.name or "").strip()
    effective_position = (position_company or "").strip() or (draft.position_company or "").strip()

    input_failure = _validate_required_inputs(
        effective_title,
        effective_name,
        effective_position,
        media_type,
        active_media,
    )
    if input_failure:
        return input_failure.model_dump()

    # Handle scenario selection from existing scenarios if provided
    resolved_direction = creative_direction
    matched_scenario_id = selected_scenario_id
    if draft.suggested_scenarios and not is_reopen:
        matched_sc, matched_scenario_id, resolved_direction = resolve_selected_scenario_prompt(
            draft.suggested_scenarios,
            selected_scenario_id=selected_scenario_id,
            creative_direction=creative_direction,
        )
    elif is_reopen:
        resolved_direction = None
        matched_scenario_id = None

    # Safety net: if creative_direction is still missing, check recent session user messages for explicit prompt
    if not resolved_direction and tool_context and hasattr(tool_context, "session") and tool_context.session:
        for ev in reversed(getattr(tool_context.session, "events", []) or []):
            if ev.author == "user" and ev.content and ev.content.parts:
                for p in ev.content.parts:
                    if p.text and "creative direction" in p.text.lower():
                        m = re.search(
                            r'creative direction:\s*["\'](.+?)["\'](?:\s*$|\s*\[|\s*\n)',
                            p.text,
                            re.DOTALL | re.IGNORECASE,
                        )
                        if m and len(m.group(1).strip()) > 20:
                            resolved_direction = m.group(1).strip()
                            break
                if resolved_direction:
                    break

    draft = merge_draft(
        draft,
        title=effective_title,
        name=effective_name,
        position_company=effective_position,
        creative_direction=resolved_direction,
        speaker_bio=speaker_bio or draft.speaker_bio,
        creative_guidance=creative_guidance or draft.creative_guidance,
        selected_scenario_id=matched_scenario_id,
        media=active_media,
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

    # If video generation is enabled and no scenario chosen yet, propose 5x2s creative scenarios
    has_existing = bool(draft.suggested_scenarios)
    should_propose = should_propose_scenarios(
        tool_context,
        media_type,
        draft.creative_direction,
        draft.selected_scenario_id,
        regenerate_scenarios,
        has_suggested_scenarios=has_existing,
        confirm_render=confirm_render,
    ) or bool(creative_guidance and not confirm_render and not selected_scenario_id)

    if should_propose:
        effective_bio = speaker_bio or draft.speaker_bio
        effective_guidance = (
            creative_guidance
            or draft.creative_guidance
            or (
                creative_direction
                if not selected_scenario_id
                and not confirm_render
                and "shot 1" not in (creative_direction or "").lower()
                else None
            )
        )
        try:
            scenarios = generate_creative_scenarios(
                talk_title=draft.title or talk_title,
                speaker_name=draft.name or name,
                position_company=draft.position_company or position_company,
                speaker_bio=effective_bio,
                creative_guidance=effective_guidance,
            )
        except Exception as e:
            print(
                f"⚠️ [video_card_tool] Scenario generation hit transient quota/model issue ({e}), using resilient fallback matrix."
            )
            from agents.video_editor.prompt_director import _build_fallback_scenarios

            scenarios = _build_fallback_scenarios(draft.title or talk_title, draft.name or name)

        draft = merge_draft(
            draft,
            title=talk_title,
            name=name,
            position_company=position_company,
            creative_direction=None,
            speaker_bio=effective_bio,
            creative_guidance=effective_guidance,
            selected_scenario_id=None,
            media=current_upload,
            suggested_scenarios=scenarios,
        )
        _save_draft(tool_context, draft)
        msg = (
            f"{format_scenarios_markdown(scenarios)}\n\n"
            "🎬 **Choose a Video Concept or Refine the Prompt:**\n"
            "Please select which scenario you would like to render (e.g. **Option 1**, **Option 2**, **Option 3**, **Option 4**, or **Option 5**), "
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
        msg = (
            f"{format_scenarios_markdown(draft.suggested_scenarios)}\n\n"
            "🎬 **Creative Video Scenarios:**\n"
            "Here is your existing video card with the 5 creative scenarios. "
            "Please select which scenario you would like to render (e.g. **Option 1**, **Option 2**, **Option 3**, **Option 4**, or **Option 5**), "
            "or adjust shots, reorder timeline, and choose styles before rendering."
        )
        return VideoCardToolResult(
            status="awaiting_confirmation",
            message=msg,
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
    tool_context.state[LAST_RENDERED_DRAFT_KEY] = draft.model_dump()
    tool_context.state[DRAFT_STATE_KEY] = {}
    raw_notice = getattr(rendered, "notice", None)
    notice = raw_notice if isinstance(raw_notice, str) else ""
    return VideoCardToolResult(
        status="success",
        message=format_render_success_message(rendered.assets, notice=notice),
        assets=rendered.assets,
        draft=draft,
    ).model_dump()
