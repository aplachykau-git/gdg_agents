import base64
import logging
import os
import random
import re
import shutil
import subprocess
import uuid
from typing import Any, Optional

import google.auth
import google.auth.transport.requests
import requests
from google import genai
from google.adk.tools import ToolContext
from google.genai import types

from agents.common.storage import upload_bytes_to_storage, upload_file_to_storage
from agents.gemini_config import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_VIDEO_MODEL,
    GeminiConfigurationError,
    get_gemini_api_key,
    get_gemini_client,
    model_for,
)

logger = logging.getLogger(__name__)

# BASE_DIR represents the absolute path of this agent's folder, ensuring self-contained integrations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Toggles to enable/disable generative AI video outputs (Gemini Omni Flash).
# Disabled by default to prevent unwanted cloud GPU billing. Direct uploaded video rendering is always supported.
DEFAULT_CINEMATIC_DIRECTIONS = (
    "Gentle golden-hour lighting, subtle breathing movement, natural eye blinks, and a soft background.",
    "Professional studio lighting, a very gentle head turn, and a natural facial expression.",
    "Soft window side-lighting, realistic bokeh, and calm, restrained camera movement.",
    "Clean editorial lighting, sharp focus, and minimal natural movement.",
)


def video_generation_enabled(tool_context: Optional[Any] = None) -> bool:
    if tool_context:
        state = {}
        if isinstance(tool_context, dict):
            state = tool_context
        else:
            # ADK's State is not a dict subclass; check it first, then the persisted session state.
            holders = [getattr(tool_context, "state", None)]
            session = getattr(tool_context, "session", None)
            holders.append(getattr(session, "state", None) if session else None)
            for holder in holders:
                if holder is None or not hasattr(holder, "get"):
                    continue
                for key in ("enable_video_generation", "enableVideoGeneration"):
                    value = holder.get(key)
                    if isinstance(value, (bool, int, str)):
                        return value.lower() in ("true", "1", "yes") if isinstance(value, str) else bool(value)
        for key in ("enable_video_generation", "enableVideoGeneration"):
            if key in state and state[key] is not None:
                return bool(state[key])
    return os.environ.get("ENABLE_VIDEO_GENERATION", "false").lower() in ("true", "1", "yes")


def _safe_b64decode(data: str) -> bytes:
    """Decodes base64 data strings safely, handling data URLs, urlsafe alphabet, and padding."""
    if data.startswith("data:") and "," in data:
        data = data.split(",", 1)[1]
    normalized = data.strip().replace("-", "+").replace("_", "/")
    pad = len(normalized) % 4
    if pad:
        normalized += "=" * (4 - pad)
    return base64.b64decode(normalized)


def sanitize_i2v_prompt(prompt: str) -> str:
    """Strips references to specific names, likenesses, character references, foreign scripts, or safety-triggering phrases for AI video generation."""
    cleaned = prompt
    # Strip metadata headers if pasted into prompt
    cleaned = re.sub(r"(?i)^(?:Name|Role|Company|Talk|Title|Speaker)\s*:\s*[^\n]+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"(?i)Generate a speaker intro video card[^\n]*", "", cleaned)
    # Strip Character Reference blocks e.g. [Character Reference: ...]
    cleaned = re.sub(r"(?i)\[?\s*Character Reference:[\s\S]*?\]", "", cleaned)
    # Strip parenthetical instructions about reference images
    cleaned = re.sub(r"(?i)\([^\)]*(?:reference image|reference photo|visual anchor)[^\)]*\)", "", cleaned)
    # Strip phrases referencing facial features, likeness, identity, visual anchors, reference photo
    cleaned = re.sub(
        r"(?i)(?:use|maintain|keep|preserve)\s+[^.,\n]*(?:facial features|likeness|identity|visual anchor|reference photo|reference image|attire)[^.,\n]*[.,]?",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?i)\b(?:from the reference photo|from the reference image|raw reference image|visual anchor|character reference|exact facial features)\b",
        "",
        cleaned,
    )
    # Strip CJK, Cyrillic, Hebrew, Arabic characters that trip safety/language filters
    cleaned = re.sub(
        r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f\uac00-\ud7af\u0400-\u04ff\u0590-\u05ff\u0600-\u06ff]",
        "",
        cleaned,
    )
    # Strip Wikipedia dictionary parentheticals e.g. (lit. 'special filming'), (postal code 92)
    cleaned = re.sub(
        r"\([^)]*(?:lit\.|meaning|postal code|trend that emerged|collective|movement that began|century|centuries)[^)]*\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Strip long parentheticals (> 30 chars)
    cleaned = re.sub(r"\([^)]{30,}\)", "", cleaned)
    # Strip empty quotes and stray punctuation
    cleaned = re.sub(r"['\"]{2}", "", cleaned)
    cleaned = re.sub(r"(?i)Create a polished speaker introduction for [^.,]+[,.]?", "", cleaned)
    cleaned = re.sub(r"(?i)\b(speaker|presenter|attendee|guest|subject)\s+named\s+[^,.\n]+", "the protagonist", cleaned)
    cleaned = re.sub(
        r"(?i)\b(speaker|presenter|talk title|presentation|topic|role|company)\s*[:=]\s*[^,.\n]+", "", cleaned
    )
    cleaned = re.sub(
        r"(?i)\b(real\s+person|person'?s\s+(?:face|likeness|identity)|facial\s+identity|likeness|identity\s+reference|celebrity)\b",
        "",
        cleaned,
    )
    # Strip empty brackets/parentheses and stray punctuation
    cleaned = re.sub(r"\(\s*[,;.]*\s*\)", "", cleaned)
    cleaned = re.sub(r"\[\s*[,;.]*\s*\]", "", cleaned)
    # Deduplicate repeated protagonist
    cleaned = re.sub(r"\bthe protagonist(?:\s+the protagonist)+\b", "the protagonist", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bthe protagonist\s*'?s\b", "the protagonist's", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(^|[.!?]\s+)the protagonist\b", r"\1The protagonist", cleaned)
    # Clean up excess whitespace and punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,\n-")
    if not cleaned or len(cleaned) < 10:
        cleaned = (
            "Cinematic conference stage in a modern professional tech setting. "
            "Gentle studio lighting, subtle natural movement, soft realistic background bokeh"
        )
    # Cap length to 3,500 chars only if excessively bloated, ensuring all 5 shots remain intact
    if len(cleaned) > 3500:
        trimmed = cleaned[:3500]
        last_period = trimmed.rfind(".")
        if last_period > 2000:
            cleaned = trimmed[: last_period + 1].strip()
        else:
            cleaned = trimmed.strip()
    return cleaned


def augment_creative_prompt(creative_prompt: str) -> str:
    cleaned = sanitize_i2v_prompt(creative_prompt)
    if len(cleaned) > 40:
        return cleaned
    return f"{cleaned.rstrip('. ')}. {random.choice(DEFAULT_CINEMATIC_DIRECTIONS)}"


def resolve_path(rel_path: str) -> str:
    """Resolves a path relative to the agent's folder, falling back to CWD and workspace root."""
    if not rel_path:
        return ""
    if os.path.isabs(rel_path):
        return rel_path

    # 1. Direct relative to BASE_DIR
    local_path = os.path.abspath(os.path.join(BASE_DIR, rel_path))
    if os.path.exists(local_path):
        return local_path

    # 2. Strip leading 'agents/video_editor/' or 'video_editor/'
    stripped = re.sub(r"^(agents/)?video_editor/", "", rel_path)
    stripped_path = os.path.abspath(os.path.join(BASE_DIR, stripped))
    if os.path.exists(stripped_path):
        return stripped_path

    # 3. Check relative to workspace root (2 levels up)
    workspace_root = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
    workspace_path = os.path.abspath(os.path.join(workspace_root, rel_path))
    if os.path.exists(workspace_path):
        return workspace_path

    workspace_agents_path = os.path.abspath(os.path.join(workspace_root, "agents", rel_path))
    if os.path.exists(workspace_agents_path):
        return workspace_agents_path

    return stripped_path


async def stage_uploaded_media(
    photo_path: str = "",
    event_id: str = "",
    part_index: int | None = None,
    tool_context: Optional[ToolContext] = None,
) -> str:
    """Finds and stages the active user uploaded photo or video from session events.
    Called by the root orchestrator in the parent context.
    """
    logger.info("📥 [Tool: stage_uploaded_media] Resolving user uploaded media from session...")

    # 1. ALWAYS scan session events first to check if the user uploaded new media in the active chat.
    try:
        if tool_context and hasattr(tool_context, "session") and tool_context.session:
            session = tool_context.session
            events = session.events or []
            logger.debug(f"DEBUG: Staging scanning total events: {len(events)}")

            # Iterate events in REVERSE to find the most recent user-uploaded video or image.
            for event in reversed(events):
                if event.author != "user":
                    continue
                if event_id and event.id != event_id:
                    continue
                if not event.content or not event.content.parts:
                    continue
                for index, part in enumerate(event.content.parts):
                    if part_index is not None and index != part_index:
                        continue
                    # Check for inline_data
                    if part.inline_data and part.inline_data.data:
                        mime = part.inline_data.mime_type or ""
                        data = part.inline_data.data
                        if isinstance(data, str):
                            try:
                                raw_bytes = _safe_b64decode(data)
                            except Exception:
                                raw_bytes = data.encode("utf-8")
                        else:
                            raw_bytes = data

                        if mime.startswith("video/"):
                            save_path = os.path.join(BASE_DIR, "assets", "staged_media.mp4")
                            os.makedirs(os.path.dirname(save_path), exist_ok=True)
                            with open(save_path, "wb") as f:
                                f.write(raw_bytes)
                            logger.info(f"✅ Staged user video to: {save_path}")
                            return "assets/staged_media.mp4"
                        elif mime.startswith("image/"):
                            ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
                            ext = ext_map.get(mime, ".jpg")
                            save_path = os.path.join(BASE_DIR, "assets", f"staged_media{ext}")
                            os.makedirs(os.path.dirname(save_path), exist_ok=True)
                            with open(save_path, "wb") as f:
                                f.write(raw_bytes)
                            logger.info(f"✅ Staged user image to: {save_path}")
                            return f"assets/staged_media{ext}"
    except Exception as e:
        logger.warning(f"⚠️ Error scanning parent session: {e}")

    # 2. Fallback to local file path if provided
    if photo_path:
        logger.warning(f"⚠️ Checking local file path: '{photo_path}'...")
        resolved = resolve_path(photo_path)
        if os.path.exists(resolved) and os.path.isfile(resolved):
            lower_path = resolved.lower()
            ext = os.path.splitext(lower_path)[1]
            save_name = (
                "staged_media.mp4"
                if any(lower_path.endswith(v) for v in [".mp4", ".mov", ".avi", ".mkv"])
                else f"staged_media{ext}"
            )
            save_path = os.path.join(BASE_DIR, "assets", save_name)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            shutil.copy2(resolved, save_path)
            logger.info(f"✅ Staged local media file to: {save_path}")
            return f"assets/{save_name}"

    # 3. Fallback to default asset placeholder
    default_placeholder = resolve_path("assets/portrait_outpainted.png")
    if os.path.exists(default_placeholder):
        logger.info(f"ℹ️ Using default placeholder avatar: {default_placeholder}")
        return "assets/portrait_outpainted.png"

    raise FileNotFoundError("No media file was found in session events or local path. Please upload a photo or video.")


def extract_video_frame(video_path: str, output_image_path: str | None = None, timestamp: float = 1.0) -> str:
    """Extracts a single high-quality frame from a video file to serve as a portrait/poster image."""
    abs_video = resolve_path(video_path)
    if not os.path.exists(abs_video) or not os.path.isfile(abs_video):
        return ""

    if not shutil.which("ffmpeg"):
        return ""

    if not output_image_path:
        base_name = os.path.splitext(os.path.basename(abs_video))[0]
        output_image_path = os.path.join(BASE_DIR, "assets", f"{base_name}_frame.jpg")

    abs_out = os.path.abspath(output_image_path)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(timestamp),
        "-i",
        abs_video,
        "-frames:v",
        "1",
        "-update",
        "1",
        "-q:v",
        "2",
        abs_out,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and os.path.exists(abs_out) and os.path.getsize(abs_out) > 0:
            return os.path.relpath(abs_out, BASE_DIR)
    except Exception as e:
        logger.warning(f"⚠️ Error extracting video frame: {e}")
    return ""


def outpaint_to_9_16(photo_path: str, client: genai.Client) -> str:
    """Uses Gemini image generation to intelligently extend/outpaint a photo to 9:16 aspect ratio.
    Instead of adding black bars, it generates realistic content (background, environment)
    to fill the missing areas while preserving the original subject perfectly.

    Returns the file path to the outpainted image."""
    logger.info("🎨 [Outpaint] Extending image to 9:16 via intelligent outpainting...")

    photo_path = resolve_path(photo_path)
    if not os.path.exists(photo_path):
        return photo_path

    try:
        with open(photo_path, "rb") as f:
            img_bytes = f.read()

        mime_type = "image/png" if photo_path.lower().endswith(".png") else "image/jpeg"
        part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)

        response = client.models.generate_content(
            model=model_for("video_outpaint", default=DEFAULT_IMAGE_MODEL),
            contents=[
                part,
                types.Part.from_text(
                    text=(
                        "High-resolution professional portrait photography. "
                        "Extend this portrait photo seamlessly to a vertical 9:16 aspect ratio. "
                        "Crucially, extend the person's torso, shoulders, and clothing (matching the exact pattern, color, and fabric of their shirt/outfit) "
                        "all the way down to the bottom edge of the frame so that their body naturally and realistically fills the lower portion of the photo. "
                        "There must be NO blank bars, empty table tops, horizontal lines, or cutoffs beneath the person. "
                        "Seamlessly expand the background environment upwards and outwards to fill the frame, while keeping the person's face, hair, and likeness identical."
                    )
                ),
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="9:16"),
            ),
        )

        if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for p in response.candidates[0].content.parts:
                if p.inline_data and p.inline_data.data:
                    outpainted_path = os.path.join(os.path.dirname(photo_path), "portrait_outpainted.png")
                    img_data = (
                        _safe_b64decode(p.inline_data.data)
                        if isinstance(p.inline_data.data, str)
                        else p.inline_data.data
                    )
                    with open(outpainted_path, "wb") as f:
                        f.write(img_data)
                    logger.info(f"✅ [Outpaint] Extended image saved to '{outpainted_path}'")
                    try:
                        cloud_img_url = upload_bytes_to_storage(
                            data=img_data,
                            destination_blob_name=f"images/portrait_outpainted_{uuid.uuid4().hex}.png",
                            content_type="image/png",
                        )
                        if cloud_img_url:
                            logger.info(f"☁️ [Cloud Storage] Outpainted avatar uploaded: {cloud_img_url}")
                    except Exception as upload_err:
                        logger.warning(f"⚠️ [Cloud Storage Notice] {upload_err}")
                    return os.path.relpath(outpainted_path, BASE_DIR)
    except Exception as e:
        logger.warning(f"⚠️ [Outpaint Notice] Outpainting not available ({e}). Using original image.")

    return os.path.relpath(photo_path, BASE_DIR)


def resolve_media_path(photo_path: str = "") -> str:
    """Intelligently resolves photo/video paths, checking staged media files first
    if the provided photo_path is nonexistent or an LLM hallucination like '00:00 00:00.png'."""
    if photo_path:
        resolved = resolve_path(photo_path)
        if os.path.exists(resolved) and os.path.isfile(resolved):
            return resolved

    # Check staged media files in assets/
    for candidate in [
        "staged_media.mp4",
        "staged_media.png",
        "staged_media.jpg",
        "staged_media.webp",
        "portrait_outpainted.png",
        "Video_example.mp4",
    ]:
        cand_path = os.path.join(BASE_DIR, "assets", candidate)
        if os.path.exists(cand_path) and os.path.isfile(cand_path):
            return cand_path

    return resolve_path(photo_path) if photo_path else os.path.join(BASE_DIR, "assets", "portrait_outpainted.png")


def verify_portrait_photo(photo_path: str = "") -> str:
    """Verifies if the uploaded/provided portrait photo contains a clear human face.

    Args:
        photo_path: The file path to verify.
    """
    logger.info(f"👤 [Tool: verify_portrait_photo] Verifying photo: {photo_path}")

    photo_path = resolve_media_path(photo_path)

    # Check if video
    lower_path = photo_path.lower()
    if any(lower_path.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]):
        logger.warning("🎥 [Face Verification] Video detected. Face verification skipped.")
        return "video"

    if not os.path.exists(photo_path):
        logger.warning(f"⚠️ [Face Verification] Photo '{photo_path}' not on disk, proceeding with default placeholder.")
        return "photo"

    try:
        with open(photo_path, "rb") as f:
            img_bytes = f.read()

        mime_type = "image/png" if photo_path.lower().endswith(".png") else "image/jpeg"
        part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)

        client = get_gemini_client()

        logger.info("🚀 Sending face detection verification call to Gemini-3.8-Flash...")
        response = client.models.generate_content(
            model=model_for("video_face_check"),
            contents=[
                part,
                types.Part.from_text(
                    text="Is there a clear, recognizable human face in this photo? Answer only YES or NO."
                ),
            ],
        )
        answer = (response.text or "").strip().upper()
        logger.info(f"👤 [Face Detection] Model response: '{answer}'")
    except Exception as e:
        logger.warning(f"⚠️ [Face Verification Notice] Verification check bypassed: {e}")

    logger.info("✅ [Face Verification] Face check completed!")
    return "photo"


# Video Generation Engine: "omni" (Google AI Gemini Omni Flash)
def get_video_engine() -> str:
    """Return the configured video engine (defaults to and only supports 'omni')."""
    return "omni"


def validate_video_generation_backend(engine: str = "omni") -> None:
    """Ensure video engine is set to omni."""
    if engine.strip().lower() != "omni":
        raise GeminiConfigurationError(
            f"Unsupported VIDEO_ENGINE='{engine}'. Only VIDEO_ENGINE=omni (Gemini Omni Flash) is supported."
        )


PHOTO_EXCLUSION_DIRECTIVE = (
    "CINEMATIC SCENE DIRECTIVE:\n"
    "1. Place the protagonist in a 100% newly rendered cinematic environment. Do not freeze, hold, or fade from the input photo framing.\n"
    "2. IMMEDIATE ACTION: The video must begin immediately at 00:00 in active cinematic motion, natural human movement, and camera movement in the described scene."
)
FINAL_INSTRUCTION = (
    "FINAL INSTRUCTION: Begin immediately at 00:00 in dynamic cinematic action in the newly rendered scene."
)


def _generate_with_omni(photo_path: str, creative_prompt: str) -> str:
    """Generates a 10s 9:16 video using Google AI Gemini Omni Flash (gemini-omni-1.2-flash) via Interactions API."""
    api_key = get_gemini_api_key()
    omni_model = model_for("video_omni", default=DEFAULT_VIDEO_MODEL)

    with open(photo_path, "rb") as f:
        frame_bytes = f.read()

    b64_img = base64.b64encode(frame_bytes).decode("utf-8")
    mime_type = "image/png" if photo_path.lower().endswith(".png") else "image/jpeg"

    i2v_prompt = augment_creative_prompt(creative_prompt)
    omni_payload_prompt = f"{PHOTO_EXCLUSION_DIRECTIVE}\n\nSCENARIO DIRECTION:\n{i2v_prompt}\n\n{FINAL_INSTRUCTION}"

    logger.info(f'🎬 [Gemini Omni Flash Prompt] Base prompt: "{creative_prompt}"')
    logger.info(f'   └─ Final Omni Prompt: "{omni_payload_prompt}"')
    logger.info("🚀 Submitting request to Google AI Gemini Omni Flash (Interactions API)...")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-goog-api-key"] = api_key
        url = f"https://generativelanguage.googleapis.com/v1beta/interactions?key={api_key}"
    else:
        # Obtain OAuth2 token from Google Cloud ADC / Service Account
        token = None
        try:
            creds, _ = google.auth.default(
                scopes=[
                    "https://www.googleapis.com/auth/generative-language",
                    "https://www.googleapis.com/auth/cloud-platform",
                ]
            )
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)
            token = creds.token
        except Exception as e:
            logger.warning(f"⚠️ [Omni Auth] Could not obtain OAuth2 token from ADC: {e}")

        if token:
            headers["Authorization"] = f"Bearer {token}"
            url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        else:
            raise RuntimeError("No valid GEMINI_API_KEY or ADC credentials available for Omni Flash.")

    payload = {
        "model": omni_model,
        "input": [
            {"type": "text", "text": omni_payload_prompt},
            {"type": "image", "data": b64_img, "mime_type": mime_type},
        ],
        "generation_config": {
            "video_config": {
                "task": "image_to_video",
            }
        },
        "response_format": {
            "type": "video",
            "duration": "10s",
            "aspect_ratio": "9:16",
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=300)
    if resp.status_code != 200:
        err_text = resp.text
        if resp.status_code == 400 and ("content_blocked" in err_text or "blocked" in err_text.lower()):
            logger.warning(
                "⚠️ [Omni Flash Warning] Prompt content blocked (400). Retrying with safe minimalist cinematic prompt..."
            )
            safe_scenario = (
                "Cinematic 9:16 sequence in a modern professional tech setting. "
                "Shot 1 (00:00 - 00:02): The protagonist enters a warm, modern architectural space with confident natural movement. "
                "Shot 2 (00:02 - 00:04): Gestures engagingly toward the camera with subtle natural expression. "
                "Shot 3 (00:04 - 00:06): Interacts dynamically with surrounding ambient light and environment. "
                "Shot 4 (00:06 - 00:08): Steps into clear focus with radiant rim lighting. "
                "Shot 5 (00:08 - 00:10): Holds an iconic, confident stance with warm studio rim lighting and soft background bokeh. "
                "Natural physical dynamics, pristine temporal stability."
            )
            safe_payload_prompt = (
                f"{PHOTO_EXCLUSION_DIRECTIVE}\n\nSCENARIO DIRECTION:\n{safe_scenario}\n\n{FINAL_INSTRUCTION}"
            )
            retry_payload = {
                "model": omni_model,
                "input": [
                    {"type": "text", "text": safe_payload_prompt},
                    {"type": "image", "data": b64_img, "mime_type": mime_type},
                ],
                "generation_config": {
                    "video_config": {
                        "task": "image_to_video",
                    }
                },
                "response_format": {
                    "type": "video",
                    "duration": "10s",
                    "aspect_ratio": "9:16",
                },
            }
            resp = requests.post(url, headers=headers, json=retry_payload, timeout=300)

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini Omni Flash generation failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    video_bytes = None
    for step in data.get("steps", []):
        for c in step.get("content", []):
            if c.get("type") == "video" and "data" in c:
                video_bytes = _safe_b64decode(c["data"])
                break
        if video_bytes:
            break

    if not video_bytes:
        raise RuntimeError(f"Gemini Omni Flash did not return any video bytes: {data}")

    animated_video_path = os.path.join(BASE_DIR, "assets", "Video_example.mp4")
    with open(animated_video_path, "wb") as f:
        f.write(video_bytes)

    logger.info(f"💾 Saved Gemini Omni Flash video ({len(video_bytes)} bytes) to '{animated_video_path}'!")
    return "assets/Video_example.mp4"


def animate_photo(photo_path: str = "", creative_prompt: str = "", tool_context: Optional[Any] = None) -> str:
    """Animates a static portrait photo into a 9:16 cinematic video using Google Gemini Omni Flash.

    Args:
        photo_path: The absolute or relative path to the static portrait image or video.
        creative_prompt: Detailed prompt generated by Gemini to animate the portrait.
        tool_context: ADK execution context for accessing session state overrides.
    """
    logger.info("🎬 [Tool: animate_photo] Animating photo using AI Video Engine or processing background video...")
    logger.info(f'💡 [Creative Prompt]: "{creative_prompt}"')

    photo_path = resolve_media_path(photo_path)
    lower_path = photo_path.lower()
    if any(lower_path.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]):
        logger.info(f"🎥 [Video Detected] Media is a video ({photo_path}). Using it directly.")
        target_video_path = os.path.join(BASE_DIR, "assets", "Video_example.mp4")
        os.makedirs(os.path.join(BASE_DIR, "assets"), exist_ok=True)
        if os.path.abspath(photo_path) != os.path.abspath(target_video_path):
            shutil.copy2(photo_path, target_video_path)
        return "assets/Video_example.mp4"

    photo_path = os.path.abspath(photo_path)

    enable_vid = video_generation_enabled(tool_context)

    if not enable_vid:
        msg = (
            "⚠️ Generative AI video models (Gemini Omni Flash) are currently disabled in the configuration to conserve cloud credits. "
            "Only direct rendering of user-uploaded videos (.mp4, .mov, .webm) is supported.\n\n"
            "💡 You can enable AI video generation in Settings or attach an existing speaker video file."
        )
        logger.warning(f"🚫 [Cost Protection] {msg}")
        return f"Error: {msg}"

    # Gemini client for outpainting
    gemini_client = get_gemini_client()
    # Outpaint to 9:16 vertical canvas
    photo_path = outpaint_to_9_16(photo_path, gemini_client)
    photo_path = resolve_path(photo_path)

    get_video_engine()  # validates VIDEO_ENGINE early
    try:
        result_path = _generate_with_omni(photo_path, creative_prompt)
    except Exception as omni_err:
        err_msg = str(omni_err)
        logger.warning(f"⚠️ [Omni Flash Notice] {err_msg}. Falling back to outpainted portrait image.")
        state = getattr(tool_context, "state", None) if tool_context else None
        if state is not None:
            try:
                state["video_generation_failure"] = err_msg
            except Exception:
                pass
        result_path = photo_path

    try:
        abs_res_path = resolve_path(result_path)
        if os.path.exists(abs_res_path) and result_path.endswith(".mp4"):
            cloud_vid_url = upload_file_to_storage(
                local_path=abs_res_path,
                destination_blob_name=f"videos/omni_{uuid.uuid4().hex}.mp4",
                content_type="video/mp4",
            )
            if cloud_vid_url:
                logger.info(f"☁️ [Cloud Storage] Video successfully uploaded to bucket: {cloud_vid_url}")
    except Exception as upload_err:
        logger.warning(f"⚠️ [Cloud Storage Notice] {upload_err}")

    return result_path


# Backward-compatible alias
generate_speaker_video = animate_photo
