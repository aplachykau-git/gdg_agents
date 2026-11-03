from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import shutil
import tempfile
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from google.adk.tools import ToolContext
from google.genai import types

from agents.common.event_series import city_from_state, default_city

from . import prompt_director, workflow
from .tools import composer_tools, media_tools
from .workflow_models import (
    CreativeScenario,
    PreparedMedia,
    RenderedAsset,
    RenderResult,
    ResolvedMedia,
    ReviewDecision,
    UploadedMedia,
    ValidatedMetadata,
    ValidationFailure,
    VideoEditorDraft,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = BASE_DIR / "workspaces"
WORKSPACE_TTL_SECONDS = int(os.getenv("VIDEO_EDITOR_WORKSPACE_TTL_SECONDS", str(24 * 3600)))
# media_tools/composer_tools resolve every path through a module-level BASE_DIR that is
# swapped per render (see _workspace_tool_paths). Renders are therefore serialised so two
# sessions can never write into each other's workspace.
_RENDER_LOCK = threading.Lock()
DEFAULT_THEME = {
    "break_color": "#4285F4",
    "circle_color": "#34A853",
    "pill_color": "#F9AB00",
    "hexagon_color": "#EA4335",
}


def _normalise(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def draft_fingerprint(draft: VideoEditorDraft) -> str:
    values = [
        draft.title or "",
        draft.name or "",
        draft.position_company or "",
        draft.creative_direction or "",
        draft.selected_scenario_id or "",
        draft.media.event_id if draft.media else "",
        str(draft.media.part_index) if draft.media else "",
    ]
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()


def missing_draft_fields(draft: VideoEditorDraft) -> list[str]:
    fields = [
        ("talk title", draft.title),
        ("speaker name", draft.name),
        ("position and company", draft.position_company),
        ("portrait image or video", draft.media),
    ]
    return [label for label, value in fields if not value]


def compile_creative_prompt(draft: VideoEditorDraft) -> str:
    assert draft.name and draft.position_company and draft.title
    direction = _normalise(draft.creative_direction)

    # Robust fallback: if creative_direction is missing but scenarios exist, resolve from selected scenario or style
    if not direction and draft.suggested_scenarios:
        sel_id = (draft.selected_scenario_id or "").strip().lower()
        matched_prompt = None
        for sc in draft.suggested_scenarios:
            if sel_id:
                if sc.id.lower() == sel_id or sel_id.startswith(sc.id.lower()):
                    matched_prompt = sc.omni_prompt
                    for st in getattr(sc, "styles", []) or []:
                        if getattr(st, "id", "").lower() == sel_id:
                            matched_prompt = getattr(st, "omni_prompt", sc.omni_prompt)
                            break
                    break
                for st in getattr(sc, "styles", []) or []:
                    if getattr(st, "id", "").lower() == sel_id:
                        matched_prompt = getattr(st, "omni_prompt", sc.omni_prompt)
                        break
                if matched_prompt:
                    break
        if not matched_prompt and draft.suggested_scenarios:
            first_sc = draft.suggested_scenarios[0]
            first_style = getattr(first_sc, "styles", [None])[0] if getattr(first_sc, "styles", None) else None
            matched_prompt = getattr(first_style, "omni_prompt", None) or first_sc.omni_prompt

        if matched_prompt:
            direction = _normalise(matched_prompt)

    if direction:
        # 1. Replace speaker full name with 'the protagonist'
        if draft.name:
            pattern = re.compile(re.escape(draft.name.strip()), re.IGNORECASE)
            direction = pattern.sub("the protagonist", direction)
            # 2. Dynamic token replacements for individual words in speaker name (e.g. "Katsiaryna", "Skwarek", "Yuliya", "Aplachykava")
            for word in draft.name.split():
                if len(word) >= 3 and word.lower() not in {"and", "the", "van", "von", "de", "del"}:
                    pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
                    direction = pattern.sub("the protagonist", direction)
            # Deduplicate repeated 'the protagonist'
            direction = re.sub(
                r"\bthe protagonist(?:\s+the protagonist)+\b", "the protagonist", direction, flags=re.IGNORECASE
            )
            direction = re.sub(r"\bthe protagonist\s*'?s\b", "the protagonist's", direction, flags=re.IGNORECASE)
            direction = re.sub(r"(^|[:.!?]\s+)the protagonist\b", r"\1The protagonist", direction)

        # 3. Clean removals of company and title if present in prompt text
        for text_to_remove in (draft.position_company, draft.title):
            if text_to_remove:
                pattern = re.compile(re.escape(text_to_remove.strip()), re.IGNORECASE)
                direction = pattern.sub("", direction)

        direction = re.sub(r"\s+", " ", direction).strip(" .,-")
    if direction:
        return direction
    return (
        "Cinematic conference speaker portrait in a modern professional setting. "
        "Subtle natural breathing movement, gentle head motion, soft realistic eye blinks, "
        "professional event atmosphere."
    )


def normalise_rendered_asset(label: str, location: str) -> RenderedAsset:
    if location.startswith(("https://", "http://", "file://")):
        return RenderedAsset(label=label, url=location)
    return RenderedAsset(label=label, url=Path(location).resolve().as_uri())


def normalise_rendered_assets(summary: str) -> list[RenderedAsset]:
    return [
        normalise_rendered_asset(asset.label, asset.url or "")
        for asset in workflow._collect_assets_from_summary(summary)
    ]


def _latest_user_upload(tool_context: ToolContext) -> UploadedMedia | None:
    for event in reversed(tool_context.session.events or []):
        if event.author != "user" or not event.content or not event.content.parts:
            continue
        for part_index, part in enumerate(event.content.parts):
            if part.inline_data and part.inline_data.data:
                return UploadedMedia(
                    event_id=event.id,
                    part_index=part_index,
                    mime_type=part.inline_data.mime_type or "",
                )
    return None


def merge_draft(
    draft: VideoEditorDraft,
    *,
    title: str | None,
    name: str | None,
    position_company: str | None,
    creative_direction: str | None,
    media: UploadedMedia | None,
    speaker_bio: str | None = None,
    creative_guidance: str | None = None,
    suggested_scenarios: list[CreativeScenario] | None = None,
    selected_scenario_id: str | None = None,
) -> VideoEditorDraft:
    updated = draft.model_copy(deep=True)
    changes = {
        "title": _normalise(title),
        "name": _normalise(name),
        "position_company": _normalise(position_company),
        "creative_direction": _normalise(creative_direction),
        "speaker_bio": _normalise(speaker_bio),
        "creative_guidance": _normalise(creative_guidance),
        "selected_scenario_id": _normalise(selected_scenario_id),
    }
    changed = False
    for field_name, value in changes.items():
        if value is not None and value != getattr(updated, field_name):
            setattr(updated, field_name, value)
            changed = True
    if suggested_scenarios is not None and suggested_scenarios != updated.suggested_scenarios:
        updated.suggested_scenarios = suggested_scenarios
        changed = True
    if media and media != updated.media:
        updated.media = media
        changed = True
    if changed:
        updated.confirmed_fingerprint = None
    return updated


def _copy_workspace_template(workspace: Path, template_name: str = "build_with_ai") -> None:
    if not workspace.is_dir():
        raise FileNotFoundError(f"Render workspace does not exist: {workspace}")

    sanitized_name = "".join(c for c in (template_name or "").lower().replace("-", "_") if c.isalnum() or c == "_")
    template_candidates = [
        BASE_DIR / "templates" / f"{sanitized_name}.html",
        BASE_DIR / "templates" / "build_with_ai.html",
        BASE_DIR / "index.html",
    ]
    template_file = next((candidate for candidate in template_candidates if candidate.is_file()), None)
    if not template_file:
        raise FileNotFoundError(f"No valid template found for '{template_name}' in {BASE_DIR / 'templates'}")

    shutil.copy2(template_file, workspace / "index.html")
    for name in ("package.json", "hyperframes.json", "meta.json"):
        source_path = BASE_DIR / name
        if source_path.is_file():
            shutil.copy2(source_path, workspace / name)
    shutil.copytree(BASE_DIR / "assets", workspace / "assets", dirs_exist_ok=True)


def prune_old_workspaces(root: Path = WORKSPACE_ROOT, ttl_seconds: int = WORKSPACE_TTL_SECONDS) -> int:
    """Delete render workspaces older than ``ttl_seconds``. Returns the number removed."""
    if ttl_seconds <= 0 or not root.is_dir():
        return 0
    cutoff = time.time() - ttl_seconds
    removed = 0
    for child in root.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


@contextmanager
def isolated_workspace(session_id: str, template_name: str = "build_with_ai") -> Iterator[Path]:
    safe_session_id = "".join(
        character if character.isalnum() or character in "-_" else "_" for character in session_id
    )
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    prune_old_workspaces()
    workspace = Path(tempfile.mkdtemp(prefix=f"{safe_session_id[:48]}-", dir=WORKSPACE_ROOT))
    _copy_workspace_template(workspace, template_name=template_name)
    yield workspace


@contextmanager
def _workspace_tool_paths(workspace: Path) -> Iterator[None]:
    original_media_base_dir = media_tools.BASE_DIR
    original_composer_base_dir = composer_tools.BASE_DIR
    media_tools.BASE_DIR = str(workspace)
    composer_tools.BASE_DIR = str(workspace)
    try:
        yield
    finally:
        media_tools.BASE_DIR = original_media_base_dir
        composer_tools.BASE_DIR = original_composer_base_dir


def _state_get(tool_context: object, key: str, default: object = None) -> object:
    """Read a key from ADK ``State`` (not a dict!) or a plain dict / session state."""
    for holder in (
        getattr(tool_context, "state", None),
        getattr(getattr(tool_context, "session", None), "state", None),
    ):
        if holder is None:
            continue
        try:
            value = holder.get(key)
        except Exception:
            continue
        if isinstance(value, (bool, int, float, str, dict, list)):
            return value
    return default


async def _review_metadata(metadata: ValidatedMetadata) -> ValidationFailure | None:
    try:
        review = await workflow._structured_response(
            ReviewDecision,
            f"""Review speaker-card metadata for a professional event.
Reject only if contradictory, malformed, unsafe, or not an identifiable speaker and role/company.
Title: {metadata.title}
Name: {metadata.name}
Position and company: {metadata.position_company}""",
        )
    except workflow.StructuredResponseError:
        # Fallback to local heuristic validation if LLM is temporarily rate-limited / unavailable:
        if (
            len(metadata.title.strip()) >= 2
            and len(metadata.name.strip()) >= 2
            and len(metadata.position_company.strip()) >= 2
        ):
            logger.warning(
                "Structured review model unavailable; fell back to local validation for '%s'",
                metadata.name,
            )
            return None
        return ValidationFailure(
            code="model_unavailable",
            message="I cannot validate the speaker details at the moment. Please try again shortly.",
            requested_action="correct_text",
            retryable=True,
        )
    if not review.approved:
        return ValidationFailure(
            code="model_unavailable",
            message=review.comment or "Please correct the speaker details.",
            requested_action="correct_text",
        )
    return None


async def _review_face(resolved_media: ResolvedMedia) -> ValidationFailure | None:
    source_path = media_tools.resolve_path(resolved_media.source_path)
    extension = os.path.splitext(source_path.lower())[1]
    mime_type = workflow.IMAGE_MIME_TYPES[extension]
    image_bytes = await asyncio.to_thread(workflow._read_binary_file, source_path)
    try:
        review = await workflow._structured_response(
            ReviewDecision,
            (
                "You are an image classifier checking if an uploaded conference speaker image contains a human being.\n"
                "CRITICAL INSTRUCTIONS:\n"
                "1. THIS IS A CONFERENCE SPEAKER AVATAR / PROFILE PHOTO, NOT A PASSPORT OR OFFICIAL GOVERNMENT ID PHOTO.\n"
                "2. DO NOT apply passport, biometric ID, or visa photo standards. Casual selfies, dark backgrounds, colored stage lighting, dramatic shadows, angled perspectives, smiles, and informal attire are ALL 100% VALID AND FULLY ACCEPTABLE.\n"
                "3. Set has_human_face=True and approved=True if ANY recognizable human face, head, or person is present in the image (even in dark lighting or casual angles).\n"
                "4. Set approved=False ONLY if the image contains NO human being at all (e.g. an image of an animal, a car, a landscape, a building, a pure diagram, a code screenshot, or abstract graphic with zero humans)."
            ),
            [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(
                    text="Does this image contain a human face or person? Return the structured review."
                ),
            ],
        )
    except workflow.StructuredResponseError:
        logger.warning(
            "Structured face review model unavailable; falling back to local image file validity for '%s'",
            source_path,
        )
        return None

    # Guard against spurious model rejections based on passport standards, lighting, background, or selfie angles
    rejection_reasons = (
        "passport",
        "official id",
        "government id",
        "visa",
        "lighting",
        "background",
        "selfie",
        "perspective",
        "angle",
        "shadow",
        "casual",
        "dark background",
        "uneven lighting",
        "plain",
        "light-colored",
    )
    comment_lower = (review.comment or "").lower()
    is_spurious_rejection = any(term in comment_lower for term in rejection_reasons)

    if not review.approved and not review.has_human_face and not is_spurious_rejection:
        return ValidationFailure(
            code="face_not_detected",
            message=review.comment or "Please upload a portrait with a clear human face.",
            requested_action="replace_media",
        )
    return None


# =============================================================================
# Framework-independent core (used by the ADK tools and by the MCP server)
# =============================================================================

RENDER_SETTING_KEYS = (
    "enable_video_generation",
    "enableVideoGeneration",
    "render_4k",
    "render4k",
    "render_gif",
    "renderGif",
    "render_ordinary",
    "renderOrdinary",
)

# Async callable that copies the source photo/video into the active render workspace
# (media_tools.BASE_DIR) and returns its path relative to that workspace.
MediaStager = Callable[[], Awaitable[str]]


@dataclass
class RenderSettings:
    """Everything the render pipeline needs besides the speaker and the media.

    ``toggles`` holds generation/output switches (``enable_video_generation``, ``render_4k``,
    ``render_gif``, ``render_ordinary``); missing keys fall back to environment defaults.
    """

    video_template: str = field(default_factory=lambda: os.getenv("VIDEO_TEMPLATE", "build_with_ai"))
    theme_colors: dict[str, str] | None = None
    toggles: dict[str, Any] = field(default_factory=dict)
    city: str = field(default_factory=default_city)

    @classmethod
    def from_tool_context(cls, tool_context: object) -> "RenderSettings":
        template = _state_get(tool_context, "video_template") or _state_get(tool_context, "videoTemplate")
        theme = _state_get(tool_context, "theme_colors")
        toggles = {key: value for key in RENDER_SETTING_KEYS if (value := _state_get(tool_context, key)) is not None}
        return cls(
            video_template=str(template or os.getenv("VIDEO_TEMPLATE", "build_with_ai")),
            theme_colors=theme if isinstance(theme, dict) else None,
            toggles=toggles,
            city=city_from_state({"community_name": _state_get(tool_context, "community_name")}),
        )


def offline_mode() -> bool:
    """VIDEO_EDITOR_OFFLINE=true: no Gemini scenario calls, no Omni, no HyperFrames.

    Scenarios come from the deterministic fallback set and renders return the bundled sample
    video, so chat, UI, MCP and evals can be exercised locally for free.
    """
    return os.getenv("VIDEO_EDITOR_OFFLINE", "false").lower() in {"1", "true", "yes"}


async def offline_render(draft: VideoEditorDraft) -> RenderResult:
    delay = float(os.getenv("VIDEO_EDITOR_OFFLINE_RENDER_SECONDS", "0") or 0)
    if delay > 0:
        await asyncio.sleep(delay)
    assets = [
        RenderedAsset(label="Video (offline sample)", url=(BASE_DIR / "assets" / "Video_example.mp4").as_uri()),
        RenderedAsset(label="Poster (offline sample)", url=(BASE_DIR / "assets" / "portrait_outpainted.png").as_uri()),
    ]
    return RenderResult(status="completed", assets=assets, summary=f"Offline render for {draft.name}")


def generate_scenarios(
    talk_title: str,
    speaker_name: str,
    position_company: str | None = None,
    speaker_bio: str | None = None,
    creative_guidance: str | None = None,
) -> list[CreativeScenario]:
    """Five cinematic scenarios with their switchable styles (blocking; run in a thread from async code)."""
    if offline_mode():
        scenarios = prompt_director._build_fallback_scenarios(talk_title, speaker_name)
    else:
        try:
            scenarios = prompt_director.generate_creative_scenarios(
                talk_title=talk_title,
                speaker_name=speaker_name,
                position_company=position_company,
                speaker_bio=speaker_bio,
                creative_guidance=creative_guidance,
            )
        except Exception as error:  # quota / model issues -> deterministic fallback
            logger.warning("Scenario generation failed (%s); using fallback scenarios.", error)
            scenarios = prompt_director._build_fallback_scenarios(talk_title, speaker_name)
    # Every scenario gets its styles up front so callers can address them by id.
    return [prompt_director._ensure_scenario_styles(sc, idx) for idx, sc in enumerate(scenarios, start=1)]


def stage_local_file(path: str | os.PathLike[str]) -> MediaStager:
    """MediaStager for a file on disk (used by the MCP server)."""
    source = Path(path).expanduser().resolve()

    async def stage() -> str:
        if not source.is_file():
            raise FileNotFoundError(f"Media file not found: {source}")
        is_video = source.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        name = "staged_media.mp4" if is_video else f"staged_media{source.suffix.lower() or '.jpg'}"
        target = Path(media_tools.BASE_DIR) / "assets" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, source, target)
        return f"assets/{name}"

    return stage


async def render_card(
    draft: VideoEditorDraft,
    settings: RenderSettings,
    *,
    stage_media: MediaStager,
    workspace_label: str = "standalone",
) -> RenderResult | ValidationFailure:
    """Validate the speaker details and render the speaker-card video. No ADK objects involved."""
    metadata_result = workflow.validate_request_metadata_fields(draft)
    if isinstance(metadata_result, ValidationFailure):
        return metadata_result
    metadata = metadata_result
    review_failure = await _review_metadata(metadata)
    if review_failure:
        return review_failure
    environment_failure = workflow.validate_render_environment()
    if environment_failure:
        return environment_failure

    # Wait for any other render (in any session) to finish without blocking the event loop.
    await asyncio.to_thread(_RENDER_LOCK.acquire)
    try:
        return await _render_locked(draft, metadata, settings, stage_media, workspace_label)
    finally:
        _RENDER_LOCK.release()


# =============================================================================
# ADK adapter
# =============================================================================


async def render_video_card(draft: VideoEditorDraft, tool_context: ToolContext) -> RenderResult | ValidationFailure:
    """Render for an ADK session: media comes from the uploaded chat attachment, settings from state."""
    if draft.media is None:
        return ValidationFailure(
            code="media_not_found",
            message="Please upload a portrait photo or a speaker video.",
            requested_action="replace_media",
        )
    media = draft.media

    async def stage_from_session() -> str:
        return await media_tools.stage_uploaded_media(
            event_id=media.event_id,
            part_index=media.part_index,
            tool_context=tool_context,
        )

    return await render_card(
        draft,
        RenderSettings.from_tool_context(tool_context),
        stage_media=stage_from_session,
        workspace_label=str(getattr(getattr(tool_context, "session", None), "id", "") or "session"),
    )


def _static_fallback_notice(failure_reason: str) -> str:
    lower = failure_reason.lower()
    if "429" in failure_reason or "spend-based rate limit" in lower or "too_many_requests" in lower:
        reason = "API spend-based rate limit exceeded (429)"
    elif "blocked" in lower:
        reason = "prompt content blocked by safety policy"
    elif failure_reason:
        reason = failure_reason[:120]
    else:
        reason = "API generation unavailable"
    return (
        f"**Note:** Background video generation via Gemini Omni Flash was unavailable ({reason}). "
        "The card was rendered using the outpainted portrait (static photo with animated titles, brackets, and DevFest badges). "
        "To get a dynamic video background, retry the render later or upload an existing speaker video (.mp4)."
    )


async def _render_locked(
    draft: VideoEditorDraft,
    metadata: ValidatedMetadata,
    settings: RenderSettings,
    stage_media: MediaStager,
    workspace_label: str,
) -> RenderResult | ValidationFailure:
    # media_tools / composer_tools read toggles from `<ctx>.state` and animate_photo reports a
    # generation failure there; a fresh per-render object means nothing leaks between renders.
    tool_context = SimpleNamespace(state=dict(settings.toggles), session=None)
    video_template = settings.video_template
    theme_colors = settings.theme_colors

    with isolated_workspace(workspace_label, template_name=video_template) as workspace:
        with _workspace_tool_paths(workspace):
            try:
                staged_path = await stage_media()
            except FileNotFoundError as missing:
                return ValidationFailure(code="media_not_found", message=str(missing), requested_action="replace_media")
            resolved_media = ResolvedMedia(
                source_path=staged_path,
                media_type=workflow.classify_media_path(staged_path),
                placeholder_used=False,
            )
            media_failure = await asyncio.to_thread(workflow.validate_resolved_media, resolved_media)
            if media_failure:
                return media_failure

            if resolved_media.media_type == "image":
                if not media_tools.video_generation_enabled(tool_context):
                    return ValidationFailure(
                        code="model_unavailable",
                        message=(
                            "Image-to-video generation is disabled. Upload a source video, or enable "
                            "AI video generation in Settings / set ENABLE_VIDEO_GENERATION=true."
                        ),
                        requested_action="replace_media",
                        retryable=False,
                    )
                face_failure = await _review_face(resolved_media)
                if face_failure:
                    return face_failure
                try:
                    # animate_photo outpaints to 9:16 itself; doing it here as well doubled cost and time.
                    video_path = await asyncio.to_thread(
                        media_tools.animate_photo,
                        photo_path=resolved_media.source_path,
                        creative_prompt=compile_creative_prompt(draft),
                        tool_context=tool_context,
                    )
                except Exception as anim_err:
                    logger.exception("Speaker animation failed")
                    return ValidationFailure(
                        code="model_unavailable",
                        message=f"Failed to generate speaker animation: {anim_err}",
                        requested_action="retry",
                        retryable=True,
                    )
                if isinstance(video_path, str) and video_path.startswith("Error:"):
                    return ValidationFailure(
                        code="model_unavailable",
                        message=video_path.removeprefix("Error:").strip(),
                        requested_action="replace_media",
                        retryable=False,
                    )
                prepared_media = PreparedMedia(
                    media_type="image",
                    source_path=resolved_media.source_path,
                    working_path=video_path,
                    video_path=video_path,
                    duration_seconds=await asyncio.to_thread(workflow._read_video_duration, video_path),
                )
            else:
                target_video_path = os.path.join(media_tools.BASE_DIR, "assets", "Video_example.mp4")
                source_path = media_tools.resolve_path(resolved_media.source_path)
                if os.path.abspath(source_path) != os.path.abspath(target_video_path):
                    await asyncio.to_thread(shutil.copy2, source_path, target_video_path)
                prepared_media = PreparedMedia(
                    media_type="video",
                    source_path=resolved_media.source_path,
                    working_path=os.path.relpath(target_video_path, media_tools.BASE_DIR),
                    video_path="assets/Video_example.mp4",
                    duration_seconds=await asyncio.to_thread(workflow._read_video_duration, "assets/Video_example.mp4"),
                )

            try:
                await asyncio.to_thread(
                    composer_tools.update_composer,
                    video_path=prepared_media.video_path,
                    title=metadata.title,
                    name=metadata.name,
                    position_company=metadata.position_company,
                    duration_seconds=prepared_media.duration_seconds,
                    theme_colors=theme_colors,
                    city=settings.city,
                )
                summary = await asyncio.to_thread(composer_tools.render_composer, tool_context=tool_context)
            except Exception as render_err:
                logger.exception("Composition render failed")
                return ValidationFailure(
                    code="render_failed",
                    message=f"Failed to render video composition: {render_err}",
                    requested_action="retry",
                )

            is_static_fallback = str(prepared_media.video_path).lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
            failure_reason = str(_state_get(tool_context, "video_generation_failure", "") or "")
            notice = _static_fallback_notice(failure_reason) if (is_static_fallback or failure_reason) else None

            return RenderResult(
                status="completed",
                assets=normalise_rendered_assets(summary),
                summary=summary,
                notice=notice,
            )
