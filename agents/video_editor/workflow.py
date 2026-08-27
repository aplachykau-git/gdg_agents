from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from collections.abc import AsyncGenerator
from typing import TypeVar

from google.adk.agents.context import Context
from google.adk.workflow import START, Workflow, node
from google.genai import types
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

try:
    from agents.bootstrap import initialise_agent_environment
except ImportError:
    from bootstrap import initialise_agent_environment

initialise_agent_environment()

from agents.gemini_config import get_gemini_client

from .tools import composer_tools, media_tools
from .workflow_models import (
    IntakeDecision,
    PreparedMedia,
    RenderedAsset,
    RenderResult,
    ResolvedMedia,
    ReviewDecision,
    ValidatedMetadata,
    ValidationFailure,
    VideoEditorRequest,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INTAKE_MODEL = "gemini-2.5-flash"
MAX_TITLE_LEN = 80
MAX_NAME_LEN = 50
MAX_POSITION_COMPANY_LEN = 80
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
DEFAULT_THEME = {
    "break_color": "#4285F4",
    "circle_color": "#34A853",
    "pill_color": "#F9AB00",
    "hexagon_color": "#EA4335",
}
INTAKE_REQUEST_STATE_KEY = "video_editor_intake_request"
INTAKE_FEEDBACK_STATE_KEY = "video_editor_intake_feedback"
SYSTEM_ERROR_PREFIX = "SYSTEM_ERROR:"
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
T = TypeVar("T", bound=BaseModel)


class StructuredResponseError(RuntimeError):
    """Raised when a structured Gemini response cannot be obtained."""


def _normalise_text(value: str | None) -> str:
    return (value or "").strip()


def _latest_user_text(ctx: Context) -> str:
    texts: list[str] = []
    for event in ctx.session.events or []:
        if event.author != "user" or not event.content or not event.content.parts:
            continue
        texts.extend(part.text for part in event.content.parts if part.text)

    for response in ctx.resume_inputs.values():
        texts.append(json.dumps(response, ensure_ascii=False) if isinstance(response, dict) else str(response))
    return "\n".join(texts[-4:])


def _has_uploaded_media(ctx: Context) -> bool:
    for event in reversed(ctx.session.events or []):
        if event.author != "user" or not event.content or not event.content.parts:
            continue
        if any(part.inline_data and part.inline_data.data for part in event.content.parts):
            return True
    return False


def _generate_structured_response(schema: type[T], prompt: str, parts: list[types.Part] | None) -> T:
    client = get_gemini_client()
    response = client.models.generate_content(
        model=INTAKE_MODEL,
        contents=parts or [types.Part.from_text(text=prompt)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,
        ),
    )
    if response.parsed is not None:
        return schema.model_validate(response.parsed)
    return schema.model_validate_json(response.text or "{}")


async def _structured_response(schema: type[T], prompt: str, parts: list[types.Part] | None = None) -> T:
    try:
        return await asyncio.to_thread(_generate_structured_response, schema, prompt, parts)
    except Exception as error:
        raise StructuredResponseError("The AI validation service is temporarily unavailable.") from error


def validate_request_metadata_fields(request: VideoEditorRequest) -> ValidatedMetadata | ValidationFailure:
    fields = [
        ("title", _normalise_text(request.title), MAX_TITLE_LEN),
        ("name", _normalise_text(request.name), MAX_NAME_LEN),
        ("position_company", _normalise_text(request.position_company), MAX_POSITION_COMPANY_LEN),
    ]
    for field_name, value, _ in fields:
        if not value:
            return ValidationFailure(
                code="missing_field",
                field=field_name,
                message=f"Missing required field: {field_name}.",
                requested_action="correct_text",
            )
    for field_name, value, limit in fields:
        if len(value) > limit:
            return ValidationFailure(
                code="field_too_long",
                field=field_name,
                message=f"{field_name} exceeds the limit of {limit} characters.",
                requested_action="correct_text",
            )
    return ValidatedMetadata(title=fields[0][1], name=fields[1][1], position_company=fields[2][1])


def classify_media_path(path: str) -> str:
    extension = os.path.splitext(path.lower())[1]
    if extension in SUPPORTED_IMAGE_EXTENSIONS:
        return "image"
    if extension in SUPPORTED_VIDEO_EXTENSIONS:
        return "video"
    return "unknown"


def _validate_image_file(path: str) -> ValidationFailure | None:
    extension = os.path.splitext(path.lower())[1]
    if extension not in IMAGE_MIME_TYPES:
        return ValidationFailure(
            code="invalid_image",
            message="Unsupported image format. Please upload PNG, JPEG, or WebP.",
            requested_action="replace_media",
        )
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, UnidentifiedImageError):
        return ValidationFailure(
            code="invalid_image",
            message="The uploaded image cannot be read. Please upload a different portrait image.",
            requested_action="replace_media",
        )
    return None


def _probe_video_file(path: str) -> ValidationFailure | None:
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        return ValidationFailure(
            code="render_environment_unavailable",
            message="Video rendering is temporarily unavailable because ffprobe is not installed.",
            requested_action="replace_media",
            retryable=False,
        )
    try:
        result = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type",
                "-of",
                "json",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ValidationFailure(
            code="invalid_video",
            message="The uploaded video took too long to inspect. Please upload a different video file.",
            requested_action="replace_media",
        )
    if result.returncode != 0:
        return ValidationFailure(
            code="invalid_video",
            message="The uploaded video cannot be read. Please upload a different video file.",
            requested_action="replace_media",
        )
    try:
        payload = json.loads(result.stdout)
        duration = float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return ValidationFailure(
            code="invalid_video",
            message="The uploaded video has no usable duration. Please upload a different video file.",
            requested_action="replace_media",
        )
    if duration <= 0 or not any(stream.get("codec_type") == "video" for stream in payload.get("streams", [])):
        return ValidationFailure(
            code="invalid_video",
            message="The uploaded file does not contain a usable video stream.",
            requested_action="replace_media",
        )
    return None


def validate_resolved_media(resolved_media: ResolvedMedia) -> ValidationFailure | None:
    if resolved_media.placeholder_used:
        return ValidationFailure(
            code="media_not_found",
            message="No uploaded image or video was found. Please upload a portrait image or a video.",
            requested_action="replace_media",
        )
    absolute_path = media_tools.resolve_path(resolved_media.source_path)
    if not os.path.exists(absolute_path) or not os.path.isfile(absolute_path):
        return ValidationFailure(
            code="media_not_found",
            message="The provided media file could not be found.",
            requested_action="replace_media",
        )
    if os.path.getsize(absolute_path) <= 0:
        return ValidationFailure(
            code="unsupported_media",
            message="The uploaded media file is empty.",
            requested_action="replace_media",
        )
    if resolved_media.media_type == "unknown":
        return ValidationFailure(
            code="unsupported_media",
            message="Unsupported media type. Please upload a portrait image or a supported video file.",
            requested_action="replace_media",
        )
    if resolved_media.media_type == "image":
        return _validate_image_file(absolute_path)
    return _probe_video_file(absolute_path)


def validate_render_environment() -> ValidationFailure | None:
    missing = [command for command in ("ffmpeg", "ffprobe", "npm", "npx") if not shutil.which(command)]
    package_file = os.path.join(BASE_DIR, "package.json")
    if missing or not os.path.isfile(package_file):
        requirements = ", ".join(missing) if missing else "the video-editor package configuration"
        return ValidationFailure(
            code="render_environment_unavailable",
            message=f"Video rendering is temporarily unavailable because {requirements} is unavailable.",
            requested_action="replace_media",
            retryable=False,
        )
    return None


def _read_video_duration(video_path: str) -> int:
    absolute_path = media_tools.resolve_path(video_path)
    if shutil.which("ffprobe") and os.path.exists(absolute_path):
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                absolute_path,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return 8 if float(result.stdout.strip()) <= 8.5 else 10
    return 8 if "video_example" in video_path.lower() else 10


def _build_creative_prompt(metadata: ValidatedMetadata, user_prompt: str | None) -> str:
    base_prompt = (
        f"Create a polished speaker intro for {metadata.name}, {metadata.position_company}, "
        f"speaking about {metadata.title}. Keep the subject realistic, calm, and in a single continuous shot."
    )
    return f"{base_prompt} {user_prompt.strip()}" if user_prompt and user_prompt.strip() else base_prompt


def _collect_assets_from_summary(summary: str) -> list[RenderedAsset]:
    assets: list[RenderedAsset] = []
    for line in summary.splitlines():
        cleaned = line.strip()
        if cleaned.startswith("• "):
            label, _, location = cleaned[2:].partition(": ")
            if location:
                assets.append(RenderedAsset(label=label.strip(), location=location.strip()))
    return assets


def _read_binary_file(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read()


@node(name="conversational_intake", rerun_on_resume=True)
async def conversational_intake_node(ctx: Context) -> AsyncGenerator[types.Content, None]:
    previous_request = VideoEditorRequest.model_validate(ctx.state.get(INTAKE_REQUEST_STATE_KEY, {}))
    feedback = str(ctx.state.get(INTAKE_FEEDBACK_STATE_KEY, ""))
    if feedback.startswith(SYSTEM_ERROR_PREFIX):
        ctx.state[INTAKE_FEEDBACK_STATE_KEY] = ""
        yield types.Content(
            role="model",
            parts=[types.Part.from_text(text=feedback.removeprefix(SYSTEM_ERROR_PREFIX).strip())],
        )
        return

    try:
        decision = await _structured_response(
            IntakeDecision,
            f"""You are the only user-facing assistant for a speaker-card video editor.
Extract fields from the latest user message and retain prior values unless corrected.
Required: talk title, speaker name, position and company, and an uploaded portrait image or video.
Ask one concise follow-up only if information is missing or correction is required. Do not say processing has started.

Prior fields: {previous_request.model_dump_json()}
Latest user input: {_latest_user_text(ctx)}
Uploaded media present: {_has_uploaded_media(ctx)}
Workflow feedback: {feedback or "None"}""",
        )
    except StructuredResponseError:
        yield types.Content(
            role="model",
            parts=[types.Part.from_text(text="I cannot process the request at the moment. Please try again shortly.")],
        )
        return
    request = VideoEditorRequest(
        title=decision.title or previous_request.title,
        name=decision.name or previous_request.name,
        position_company=decision.position_company or previous_request.position_company,
        creative_prompt=decision.creative_prompt or previous_request.creative_prompt,
    )
    ctx.state[INTAKE_REQUEST_STATE_KEY] = request.model_dump()
    missing_fields = [
        label
        for label, value in (
            ("talk title", request.title),
            ("speaker name", request.name),
            ("position and company", request.position_company),
        )
        if not _normalise_text(value)
    ]
    if feedback or missing_fields or not _has_uploaded_media(ctx):
        ctx.state[INTAKE_FEEDBACK_STATE_KEY] = ""
        fallback = f"Please provide {', '.join(missing_fields)}." if missing_fields else feedback
        if not _has_uploaded_media(ctx):
            fallback = f"{fallback.rstrip('.')} Please also upload a portrait image or video."
        yield types.Content(
            role="model",
            parts=[types.Part.from_text(text=decision.user_message or fallback)],
        )
        return
    ctx.route = "ready"


@node(name="validate_input_model")
def validate_input_model_node(ctx: Context) -> None:
    request = VideoEditorRequest.model_validate(ctx.state[INTAKE_REQUEST_STATE_KEY])
    result = validate_request_metadata_fields(request)
    if isinstance(result, ValidationFailure):
        ctx.state[INTAKE_FEEDBACK_STATE_KEY] = result.message
        ctx.route = "invalid"
        return
    ctx.state["temp:validated_metadata"] = result.model_dump()
    ctx.route = "valid"


@node(name="stage_media")
async def stage_media_node(ctx: Context) -> None:
    staged_path = await media_tools.stage_uploaded_media(tool_context=ctx)
    ctx.state["temp:resolved_media"] = ResolvedMedia(
        source_path=staged_path,
        media_type=classify_media_path(staged_path),
        placeholder_used=staged_path == "assets/portrait_outpainted.png",
    ).model_dump()


@node(name="validate_media_model")
async def validate_media_model_node(ctx: Context) -> None:
    resolved_media = ResolvedMedia.model_validate(ctx.state["temp:resolved_media"])
    failure = await asyncio.to_thread(validate_resolved_media, resolved_media)
    if failure:
        prefix = SYSTEM_ERROR_PREFIX if failure.code == "render_environment_unavailable" else ""
        ctx.state[INTAKE_FEEDBACK_STATE_KEY] = f"{prefix}{failure.message}"
        ctx.route = "invalid"
        return
    ctx.route = "valid"


@node(name="validate_render_environment")
def validate_render_environment_node(ctx: Context) -> None:
    failure = validate_render_environment()
    if failure:
        ctx.state[INTAKE_FEEDBACK_STATE_KEY] = f"{SYSTEM_ERROR_PREFIX}{failure.message}"
        ctx.route = "invalid"
        return
    ctx.route = "valid"


@node(name="review_metadata")
async def review_metadata_node(ctx: Context) -> None:
    metadata = ValidatedMetadata.model_validate(ctx.state["temp:validated_metadata"])
    try:
        review = await _structured_response(
            ReviewDecision,
            f"""Review speaker-card metadata for a professional event.
Reject only if contradictory, malformed, unsafe, or not an identifiable speaker and role/company.
Title: {metadata.title}
Name: {metadata.name}
Position and company: {metadata.position_company}""",
        )
    except StructuredResponseError:
        ctx.state[INTAKE_FEEDBACK_STATE_KEY] = (
            f"{SYSTEM_ERROR_PREFIX}I cannot validate the speaker details at the moment. Please try again shortly."
        )
        ctx.route = "invalid"
        return
    if not review.approved:
        ctx.state[INTAKE_FEEDBACK_STATE_KEY] = review.comment or "Please correct the speaker details."
        ctx.route = "invalid"
        return
    ctx.route = "valid"


@node(name="classify_media")
def classify_media_node(ctx: Context) -> None:
    ctx.route = ResolvedMedia.model_validate(ctx.state["temp:resolved_media"]).media_type


@node(name="review_face")
async def review_face_node(ctx: Context) -> None:
    resolved_media = ResolvedMedia.model_validate(ctx.state["temp:resolved_media"])
    absolute_path = media_tools.resolve_path(resolved_media.source_path)
    extension = os.path.splitext(absolute_path.lower())[1]
    mime_type = IMAGE_MIME_TYPES[extension]
    image_bytes = await asyncio.to_thread(_read_binary_file, absolute_path)
    try:
        review = await _structured_response(
            ReviewDecision,
            "Approve only if this portrait contains a clear, recognisable human face suitable for a speaker card.",
            [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text="Return the structured review."),
            ],
        )
    except StructuredResponseError:
        ctx.state[INTAKE_FEEDBACK_STATE_KEY] = (
            f"{SYSTEM_ERROR_PREFIX}I cannot validate the portrait at the moment. Please try again shortly."
        )
        ctx.route = "invalid"
        return
    if not review.approved:
        ctx.state[INTAKE_FEEDBACK_STATE_KEY] = review.comment or "Please upload a portrait with a clear human face."
        ctx.route = "invalid"
        return
    ctx.route = "valid"


@node(name="outpaint_image")
def outpaint_image_node(ctx: Context) -> None:
    source_path = ResolvedMedia.model_validate(ctx.state["temp:resolved_media"]).source_path
    client = get_gemini_client()
    ctx.state["temp:outpainted_image_path"] = media_tools.outpaint_to_9_16(source_path, client)


@node(name="build_creative_prompt")
def build_creative_prompt_node(ctx: Context) -> None:
    metadata = ValidatedMetadata.model_validate(ctx.state["temp:validated_metadata"])
    request = VideoEditorRequest.model_validate(ctx.state[INTAKE_REQUEST_STATE_KEY])
    ctx.state["temp:creative_prompt"] = _build_creative_prompt(metadata, request.creative_prompt)


@node(name="generate_video_from_image")
def generate_video_from_image_node(ctx: Context) -> None:
    video_path = media_tools.animate_photo(
        photo_path=str(ctx.state["temp:outpainted_image_path"]),
        creative_prompt=str(ctx.state["temp:creative_prompt"]),
    )
    resolved_media = ResolvedMedia.model_validate(ctx.state["temp:resolved_media"])
    ctx.state["temp:prepared_media"] = PreparedMedia(
        media_type="image",
        source_path=resolved_media.source_path,
        working_path=str(ctx.state["temp:outpainted_image_path"]),
        video_path=video_path,
        duration_seconds=_read_video_duration(video_path),
    ).model_dump()


@node(name="normalise_input_video")
def normalise_input_video_node(ctx: Context) -> None:
    resolved_media = ResolvedMedia.model_validate(ctx.state["temp:resolved_media"])
    target_video_path = os.path.join(BASE_DIR, "assets", "Video_example.mp4")
    os.makedirs(os.path.dirname(target_video_path), exist_ok=True)
    source_path = media_tools.resolve_path(resolved_media.source_path)
    if os.path.abspath(source_path) != os.path.abspath(target_video_path):
        shutil.copy2(source_path, target_video_path)
    ctx.state["temp:prepared_media"] = PreparedMedia(
        media_type="video",
        source_path=resolved_media.source_path,
        working_path=os.path.relpath(target_video_path, BASE_DIR),
        video_path="assets/Video_example.mp4",
        duration_seconds=_read_video_duration("assets/Video_example.mp4"),
    ).model_dump()


@node(name="prepare_render_input")
def prepare_render_input_node(ctx: Context) -> None:
    prepared_media = PreparedMedia.model_validate(ctx.state["temp:prepared_media"])
    ctx.state["temp:render_plan"] = {"theme": DEFAULT_THEME, "duration_seconds": prepared_media.duration_seconds}


@node(name="update_composer")
def update_composer_node(ctx: Context) -> None:
    metadata = ValidatedMetadata.model_validate(ctx.state["temp:validated_metadata"])
    prepared_media = PreparedMedia.model_validate(ctx.state["temp:prepared_media"])
    render_plan = dict(ctx.state["temp:render_plan"])
    composer_tools.update_composer(
        video_path=prepared_media.video_path,
        title=metadata.title,
        name=metadata.name,
        position_company=metadata.position_company,
        duration_seconds=render_plan["duration_seconds"],
        theme_colors=render_plan["theme"],
    )


@node(name="render_outputs")
def render_outputs_node(ctx: Context) -> None:
    summary = composer_tools.render_composer()
    ctx.state["temp:render_result"] = RenderResult(
        status="completed",
        assets=_collect_assets_from_summary(summary),
        summary=summary,
    ).model_dump()


@node(name="publish_outputs")
async def publish_outputs_node(ctx: Context) -> AsyncGenerator[types.Content, None]:
    result = RenderResult.model_validate(ctx.state["temp:render_result"])
    ctx.state[INTAKE_REQUEST_STATE_KEY] = {}
    ctx.state[INTAKE_FEEDBACK_STATE_KEY] = ""
    yield types.Content(
        role="model",
        parts=[types.Part.from_text(text=result.summary)],
    )


video_editor_workflow = Workflow(
    name="video_editor",
    description="Standalone conversational video-editor workflow.",
    output_schema=RenderResult,
    edges=[
        (START, conversational_intake_node),
        (conversational_intake_node, {"ready": validate_input_model_node}),
        (validate_input_model_node, {"valid": stage_media_node, "invalid": conversational_intake_node}),
        (stage_media_node, validate_media_model_node),
        (validate_media_model_node, {"valid": validate_render_environment_node, "invalid": conversational_intake_node}),
        (validate_render_environment_node, {"valid": review_metadata_node, "invalid": conversational_intake_node}),
        (review_metadata_node, {"valid": classify_media_node, "invalid": conversational_intake_node}),
        (classify_media_node, {"image": review_face_node, "video": normalise_input_video_node}),
        (review_face_node, {"valid": outpaint_image_node, "invalid": conversational_intake_node}),
        (outpaint_image_node, build_creative_prompt_node, generate_video_from_image_node),
        (
            (generate_video_from_image_node, normalise_input_video_node),
            prepare_render_input_node,
            update_composer_node,
            render_outputs_node,
            publish_outputs_node,
        ),
    ],
)
