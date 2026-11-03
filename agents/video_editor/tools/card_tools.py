"""Conversational tools of the speaker-card video editor.

Instead of one tool with a dozen flags, the agent gets a few small tools whose names
match what the user wants to do. All of them share the persistent ``CardSession``
(see ``card_session.py``) so the speaker, photo and scenarios survive renders.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from google.adk.tools import ToolContext

from agents.common import ui_payloads

from ..card_session import (
    CardSession,
    RenderRecord,
    attach_latest_upload,
    load_session,
    pop_ui_selection,
    save_session,
    update_speaker_fields,
)
from ..video_card_service import (
    _latest_user_upload,
    generate_scenarios,
    offline_mode,
    offline_render,
    render_video_card,
)
from ..workflow_models import (
    CreativeScenario,
    ValidationFailure,
    VideoCardToolResult,
    VideoEditorDraft,
)
from .video_card_tool import format_render_success_message, resolve_selected_scenario_prompt

logger = logging.getLogger(__name__)

RETRY_CODES = {"render_failed", "model_unavailable", "render_environment_unavailable"}
MEDIA_CODES = {"media_not_found", "unsupported_media", "invalid_image", "invalid_video", "face_not_detected"}


# --------------------------------------------------------------------------- helpers


def _require_context(tool_context: ToolContext | None) -> ToolContext:
    if tool_context is None:
        raise ValueError("tool_context is required.")
    return tool_context


def _last_user_event_id(tool_context: ToolContext) -> str | None:
    session = getattr(tool_context, "session", None)
    for event in reversed(getattr(session, "events", None) or []):
        if getattr(event, "author", None) == "user":
            return getattr(event, "id", None)
    return None


def _open(tool_context: ToolContext) -> CardSession:
    session = load_session(tool_context.state)
    attach_latest_upload(session, _latest_user_upload(tool_context))
    return session


def _result(session: CardSession, **kwargs: Any) -> dict:
    result = VideoCardToolResult(speaker=session.speaker.summary(), **kwargs)
    return result.model_dump(mode="json", exclude_none=True, exclude_defaults=False)


def _scenario_index(session: CardSession) -> str:
    lines = []
    for idx, sc in enumerate(session.scenarios, start=1):
        styles = ", ".join(f"{st.name} [{st.id}]" for st in sc.styles) or "default"
        lines.append(f"{idx}. {sc.title} — {sc.genre} (id: {sc.id}; styles: {styles})")
    return "\n".join(lines)


def _same_scenario(session: CardSession, option: str, scenario_id: str) -> bool:
    """True when ``option`` (a number like "2" / "Option 2" or an id) refers to ``scenario_id``."""
    matched, _, _ = resolve_selected_scenario_prompt(session.scenarios, selected_scenario_id=option)
    return bool(matched and matched.id.lower() == scenario_id.lower()) or option.strip().lower() == scenario_id.lower()


def _missing_result(session: CardSession, missing: list[str]) -> dict:
    return _result(
        session,
        status="error",
        code="missing_input",
        message=f"Still missing: {', '.join(missing)}.",
        requested_action="replace_media" if missing == ["portrait photo or video"] else "provide_details",
        missing_fields=missing,
        next_step="Ask the user only for the missing items, then call update_speaker (photos/videos are picked up automatically).",
    )


def _next_step_for(session: CardSession) -> str:
    missing = session.speaker.missing_fields()
    if missing:
        return f"Ask the user for: {', '.join(missing)}."
    if session.speaker.media_kind == "video":
        return "Everything is ready. Call render_video."
    if not session.scenarios:
        return "Everything is ready. Call propose_scenarios."
    return "Scenarios already exist. The user can pick one (render_video) or ask for new ones (propose_scenarios)."


def _failure_to_result(session: CardSession, failure: ValidationFailure) -> dict:
    if failure.code in MEDIA_CODES:
        action, hint = "replace_media", "Ask the user for a different photo or video."
    elif failure.requested_action == "correct_text":
        action, hint = "correct_text", "Ask the user to correct the text fields, then call update_speaker."
    elif failure.retryable or failure.code in RETRY_CODES:
        action, hint = (
            "retry",
            "Nothing is lost. Offer to try the same render again (call render_video with the same option).",
        )
    else:
        action, hint = failure.requested_action if failure.requested_action != "retry_render" else "retry", ""
    return _result(
        session,
        status="error",
        code=failure.code,
        message=failure.message,
        retryable=failure.retryable,
        requested_action=action,
        next_step=hint or None,
    )


async def _generate_scenarios(session: CardSession, guidance: str | None) -> list[CreativeScenario]:
    speaker = session.speaker
    return await asyncio.to_thread(
        generate_scenarios,
        talk_title=speaker.title or "",
        speaker_name=speaker.name or "",
        position_company=speaker.position_company,
        speaker_bio=speaker.speaker_bio,
        creative_guidance=guidance,
    )


# --------------------------------------------------------------------------- tools


async def update_speaker(
    talk_title: str | None = None,
    name: str | None = None,
    position_company: str | None = None,
    speaker_bio: str | None = None,
    new_speaker: bool = False,
    tool_context: ToolContext | None = None,
) -> dict:
    """Save or change the speaker-card details. Pass only the fields the user gave or changed.

    Uploaded photos/videos are attached automatically; there is no need to pass them.
    The speaker stays saved after renders, so do not call this just to re-render.

    Args:
        talk_title: Talk title shown on the card.
        name: Speaker full name.
        position_company: Position and company, e.g. "GDE, Google".
        speaker_bio: Bio or talk abstract, used to tailor the scenarios.
        new_speaker: True ONLY when the user wants a card for a different person; clears the previous speaker.
    """
    ctx = _require_context(tool_context)
    session = load_session(ctx.state)
    latest = _latest_user_upload(ctx)
    uploaded_now = bool(latest and latest.event_id == _last_user_event_id(ctx))
    changed = update_speaker_fields(
        session,
        title=talk_title,
        name=name,
        position_company=position_company,
        speaker_bio=speaker_bio,
        new_speaker=new_speaker,
        keep_media=uploaded_now and latest == session.speaker.media,
    )
    if new_speaker and latest and not uploaded_now:
        session.ignored_upload = latest
    attach_latest_upload(session, latest)
    save_session(ctx.state, session)

    missing = session.speaker.missing_fields()
    note = ""
    if session.scenarios and {"title", "speaker_bio"} & set(changed):
        note = " Existing scenarios were written for the previous details; offer to regenerate them."
    return _result(
        session,
        status="ok",
        message=(f"Saved: {', '.join(changed)}." if changed else "No changes.") + note,
        missing_fields=missing,
        requested_action="provide_details" if missing else None,
        next_step=_next_step_for(session),
    )


async def propose_scenarios(
    creative_guidance: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Invent 5 fresh cinematic scenarios (5 shots x 2s) for the saved speaker photo.

    Use it for the first proposal and whenever the user wants new/different ideas.
    The scenarios are shown to the user as interactive cards by the UI.

    Args:
        creative_guidance: Optional vibe/style wish, e.g. "like a Nike ad", "more humour", "cyberpunk".
    """
    ctx = _require_context(tool_context)
    session = _open(ctx)
    missing = session.speaker.missing_fields()
    if missing:
        save_session(ctx.state, session)
        return _missing_result(session, missing)
    if session.speaker.media_kind == "video":
        save_session(ctx.state, session)
        return _result(
            session,
            status="error",
            code="not_applicable",
            message="The source is a video, so no AI scenarios are needed.",
            next_step="Call render_video to render the card with the uploaded video.",
        )

    guidance = (creative_guidance or "").strip() or None
    session.scenarios = await _generate_scenarios(session, guidance)
    session.creative_guidance = guidance
    save_session(ctx.state, session)
    return _result(
        session,
        status="awaiting_scenario_selection",
        message="Proposed scenarios (the user sees them as interactive cards):\n" + _scenario_index(session),
        requested_action="select_scenario",
        scenarios=session.scenarios,
        next_step=(
            "Briefly tell the user the options are ready (one line per option at most) and ask which one to render. "
            "Do not repeat shot tables."
        ),
    )


async def show_scenarios(tool_context: ToolContext | None = None) -> dict:
    """Show the already proposed scenarios again (e.g. 'reopen the card', 'show the options again')."""
    ctx = _require_context(tool_context)
    session = _open(ctx)
    save_session(ctx.state, session)
    if not session.scenarios:
        return _result(
            session,
            status="error",
            code="no_scenarios",
            message="No scenarios have been proposed yet.",
            next_step=_next_step_for(session),
        )
    return _result(
        session,
        status="awaiting_scenario_selection",
        message="Showing the saved scenarios again:\n" + _scenario_index(session),
        requested_action="select_scenario",
        scenarios=session.scenarios,
    )


async def render_video(
    option: str | None = None,
    style_id: str | None = None,
    custom_direction: str | None = None,
    tool_context: ToolContext | None = None,
) -> dict:
    """Render the speaker-card video for the saved speaker.

    Can be called again and again (another option, another style, after editing text)
    without re-entering anything.

    Args:
        option: Chosen scenario, its number ("2") or id. Not needed for a speaker video.
        style_id: Optional style id of the chosen scenario.
        custom_direction: Only when the user wrote or edited their own storyboard/prompt.
            Visual description only: no names, companies or talk titles.
    """
    ctx = _require_context(tool_context)
    session = _open(ctx)
    missing = session.speaker.missing_fields()
    if missing:
        save_session(ctx.state, session)
        return _missing_result(session, missing)

    ui = pop_ui_selection(ctx.state)
    if ui and (option is None or _same_scenario(session, option, ui.scenario_id)):
        option = ui.scenario_id
        style_id = style_id or ui.style_id
        if ui.edited and ui.prompt and not custom_direction:
            custom_direction = ui.prompt

    direction: str | None = (custom_direction or "").strip() or None
    selected_id: str | None = None
    label = "Custom direction" if direction else "Uploaded video"

    if session.speaker.media_kind == "image":
        if option or style_id:
            matched, selected_id, resolved = resolve_selected_scenario_prompt(
                session.scenarios,
                selected_scenario_id=(style_id or option),
                creative_direction=direction,
            )
            if matched is None and style_id and option:
                matched, selected_id, resolved = resolve_selected_scenario_prompt(
                    session.scenarios, selected_scenario_id=option, creative_direction=direction
                )
            if matched is None and not direction:
                save_session(ctx.state, session)
                return _result(
                    session,
                    status="error",
                    code="unknown_option",
                    message=f"Option '{style_id or option}' was not found.",
                    requested_action="select_scenario",
                    next_step="Ask which option to render. Available:\n" + (_scenario_index(session) or "none"),
                )
            if matched is not None:
                label = matched.title
                # A prompt the user wrote or edited always wins over the stored scenario prompt.
                direction = direction or resolved
        elif not direction:
            save_session(ctx.state, session)
            if session.scenarios:
                return _result(
                    session,
                    status="error",
                    code="scenario_not_selected",
                    message="No scenario was chosen.",
                    requested_action="select_scenario",
                    next_step="Ask the user which option to render:\n" + _scenario_index(session),
                )
            return _result(
                session,
                status="error",
                code="no_scenarios",
                message="There are no scenarios yet.",
                next_step="Call propose_scenarios first (or ask the user for their own storyboard).",
            )

    speaker = session.speaker
    draft = VideoEditorDraft(
        title=speaker.title,
        name=speaker.name,
        position_company=speaker.position_company,
        speaker_bio=speaker.speaker_bio,
        creative_direction=direction,
        media=speaker.media,
        suggested_scenarios=session.scenarios,
        selected_scenario_id=selected_id,
    )
    rendered = await (offline_render(draft) if offline_mode() else render_video_card(draft, ctx))
    if isinstance(rendered, ValidationFailure):
        save_session(ctx.state, session)
        return _failure_to_result(session, rendered)

    notice = rendered.notice if isinstance(rendered.notice, str) else ""
    session.renders.append(
        RenderRecord(
            label=label,
            scenario_id=selected_id,
            creative_direction=direction,
            assets=rendered.assets,
            notice=notice or None,
        )
    )
    save_session(ctx.state, session)
    return _result(
        session,
        status="success",
        message=format_render_success_message(rendered.assets, notice=notice),
        assets=rendered.assets,
        ui=ui_payloads.media(
            [asset.model_dump(mode="json") for asset in rendered.assets],
            speaker=session.speaker.summary(),
            notice=notice,
        ),
        next_step=(
            "Share the links. The speaker, photo and scenarios are still saved: the user can render another "
            "option or style, ask for new scenarios, or change any text."
        ),
    )


async def get_card_status(tool_context: ToolContext | None = None) -> dict:
    """Return what is saved so far: speaker details, photo, scenarios and previous renders."""
    ctx = _require_context(tool_context)
    session = _open(ctx)
    save_session(ctx.state, session)
    renders = [
        {"label": r.label, "assets": [a.model_dump(exclude_none=True) for a in r.assets]} for r in session.renders
    ]
    return _result(
        session,
        status="ok",
        message=(f"Scenarios:\n{_scenario_index(session) or 'none'}\nRenders so far: {len(renders)}."),
        missing_fields=session.speaker.missing_fields(),
        next_step=_next_step_for(session),
    ) | {"renders": renders}


ALL_TOOLS = [update_speaker, propose_scenarios, show_scenarios, render_video, get_card_status]
