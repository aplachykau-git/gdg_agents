from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from google.adk.tools import ToolContext
from google.genai import types

from agents.gemini_config import get_gemini_client

from . import workflow
from .tools import composer_tools, media_tools
from .workflow_models import (
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

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = BASE_DIR / "workspaces"
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
    if direction:
        # 1. Full string removals
        for text_to_remove in (draft.name, draft.position_company, draft.title):
            if text_to_remove:
                pattern = re.compile(re.escape(text_to_remove), re.IGNORECASE)
                direction = pattern.sub("", direction)
        # 2. Dynamic token removals for individual words in speaker name (e.g. "Katsiaryna", "Skwarek")
        if draft.name:
            for word in draft.name.split():
                if len(word) >= 3:
                    pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
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
) -> VideoEditorDraft:
    updated = draft.model_copy(deep=True)
    changes = {
        "title": _normalise(title),
        "name": _normalise(name),
        "position_company": _normalise(position_company),
        "creative_direction": _normalise(creative_direction),
    }
    changed = False
    for field, value in changes.items():
        if value is not None and value != getattr(updated, field):
            setattr(updated, field, value)
            changed = True
    if media and media != updated.media:
        updated.media = media
        changed = True
    if changed:
        updated.confirmed_fingerprint = None
    return updated


def _copy_workspace_template(workspace: Path) -> None:
    if not workspace.is_dir():
        raise FileNotFoundError(f"Render workspace does not exist: {workspace}")
    for name in ("index.html", "package.json", "hyperframes.json", "meta.json"):
        shutil.copy2(BASE_DIR / name, workspace / name)
    shutil.copytree(BASE_DIR / "assets", workspace / "assets", dirs_exist_ok=True)


@contextmanager
def isolated_workspace(session_id: str) -> Iterator[Path]:
    safe_session_id = "".join(
        character if character.isalnum() or character in "-_" else "_" for character in session_id
    )
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=f"{safe_session_id[:48]}-", dir=WORKSPACE_ROOT))
    _copy_workspace_template(workspace)
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
            "Approve only if this portrait contains a clear, recognisable human face suitable for a speaker card.",
            [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text="Return the structured review."),
            ],
        )
    except workflow.StructuredResponseError:
        return ValidationFailure(
            code="model_unavailable",
            message="I cannot validate the portrait at the moment. Please try again shortly.",
            requested_action="replace_media",
            retryable=True,
        )
    if not review.approved:
        return ValidationFailure(
            code="face_not_detected",
            message=review.comment or "Please upload a portrait with a clear human face.",
            requested_action="replace_media",
        )
    return None


async def render_video_card(draft: VideoEditorDraft, tool_context: ToolContext) -> RenderResult | ValidationFailure:
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
    assert draft.media

    with isolated_workspace(tool_context.session.id) as workspace:
        with _workspace_tool_paths(workspace):
            staged_path = await media_tools.stage_uploaded_media(
                event_id=draft.media.event_id,
                part_index=draft.media.part_index,
                tool_context=tool_context,
            )
            resolved_media = ResolvedMedia(
                source_path=staged_path,
                media_type=workflow.classify_media_path(staged_path),
                placeholder_used=False,
            )
            media_failure = await asyncio.to_thread(workflow.validate_resolved_media, resolved_media)
            if media_failure:
                return media_failure

            if resolved_media.media_type == "image":
                if not media_tools.video_generation_enabled():
                    return ValidationFailure(
                        code="model_unavailable",
                        message=(
                            "Image-to-video generation is disabled. Upload a source video or set "
                            "ENABLE_VIDEO_GENERATION=true."
                        ),
                        requested_action="replace_media",
                        retryable=False,
                    )
                face_failure = await _review_face(resolved_media)
                if face_failure:
                    return face_failure
                source_path = media_tools.outpaint_to_9_16(resolved_media.source_path, get_gemini_client())
                video_path = media_tools.animate_photo(
                    photo_path=source_path,
                    creative_prompt=compile_creative_prompt(draft),
                )
                prepared_media = PreparedMedia(
                    media_type="image",
                    source_path=resolved_media.source_path,
                    working_path=source_path,
                    video_path=video_path,
                    duration_seconds=workflow._read_video_duration(video_path),
                )
            else:
                target_video_path = os.path.join(media_tools.BASE_DIR, "assets", "Video_example.mp4")
                source_path = media_tools.resolve_path(resolved_media.source_path)
                if os.path.abspath(source_path) != os.path.abspath(target_video_path):
                    shutil.copy2(source_path, target_video_path)
                prepared_media = PreparedMedia(
                    media_type="video",
                    source_path=resolved_media.source_path,
                    working_path=os.path.relpath(target_video_path, media_tools.BASE_DIR),
                    video_path="assets/Video_example.mp4",
                    duration_seconds=workflow._read_video_duration("assets/Video_example.mp4"),
                )

            composer_tools.update_composer(
                video_path=prepared_media.video_path,
                title=metadata.title,
                name=metadata.name,
                position_company=metadata.position_company,
                duration_seconds=prepared_media.duration_seconds,
                theme_colors=DEFAULT_THEME,
            )
            summary = composer_tools.render_composer()
            return RenderResult(
                status="completed",
                assets=normalise_rendered_assets(summary),
                summary=summary,
            )
