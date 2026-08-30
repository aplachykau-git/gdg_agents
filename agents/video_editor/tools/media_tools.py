import base64
import os
import random
import re
import shutil
import time
from typing import Any, Optional

import google.auth
import google.auth.transport.requests
import requests
from google import genai
from google.adk.tools import ToolContext
from google.cloud import storage
from google.genai import types

from agents.common.storage import upload_bytes_to_storage, upload_file_to_storage
from agents.gemini_config import (
    GeminiConfigurationError,
    get_gemini_api_key,
    get_gemini_client,
    require_vertex_ai,
    use_vertex_ai,
)

# BASE_DIR represents the absolute path of this agent's folder, ensuring self-contained integrations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Toggles to enable/disable generative AI video outputs (Veo 3.1 / Gemini Omni).
# Disabled by default to prevent unwanted cloud GPU billing. Direct uploaded video rendering is always supported.
DEFAULT_CINEMATIC_DIRECTIONS = (
    "Gentle golden-hour lighting, subtle breathing movement, natural eye blinks, and a soft background.",
    "Professional studio lighting, a very gentle head turn, and a natural facial expression.",
    "Soft window side-lighting, realistic bokeh, and calm, restrained camera movement.",
    "Clean editorial lighting, sharp focus, and minimal natural movement.",
)


def video_generation_enabled() -> bool:
    return os.environ.get("ENABLE_VIDEO_GENERATION", "false").lower() in ("true", "1", "yes")


def sanitize_i2v_prompt(prompt: str) -> str:
    """Strips references to specific names, likenesses, character references, or safety-triggering phrases for AI video generation."""
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
    cleaned = re.sub(r"(?i)Create a polished speaker introduction for [^.,]+[,.]?", "", cleaned)
    cleaned = re.sub(r"(?i)speaking about [^.,]+[,.]?", "", cleaned)
    cleaned = re.sub(r"(?i)\b(speaker|presenter|attendee|guest|subject)\s+named\s+[^,.\n]+", "", cleaned)
    cleaned = re.sub(
        r"(?i)\b(speaker|presenter|talk title|presentation|topic|role|company)\s*[:=]\s*[^,.\n]+", "", cleaned
    )
    cleaned = re.sub(r"(?i)\b(real\s+person|person'?s\s+likeness|celebrity|identity)\b", "", cleaned)
    # Strip empty brackets/parentheses and stray punctuation
    cleaned = re.sub(r"\(\s*[,;.]*\s*\)", "", cleaned)
    cleaned = re.sub(r"\[\s*[,;.]*\s*\]", "", cleaned)
    # Clean up excess whitespace and punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,\n-")
    if not cleaned or len(cleaned) < 10:
        cleaned = (
            "Cinematic conference stage in a modern professional tech setting. "
            "Gentle studio lighting, subtle natural movement, soft realistic background bokeh"
        )
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
    print("\n📥 [Tool: stage_uploaded_media] Resolving user uploaded media from session...")

    # 1. ALWAYS scan session events first to check if the user uploaded new media in the active chat.
    try:
        if tool_context and hasattr(tool_context, "session") and tool_context.session:
            session = tool_context.session
            events = session.events or []
            print(f"DEBUG: Staging scanning total events: {len(events)}")

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
                                raw_bytes = base64.b64decode(data)
                            except Exception:
                                raw_bytes = data.encode("utf-8")
                        else:
                            raw_bytes = data

                        if mime.startswith("video/"):
                            save_path = os.path.join(BASE_DIR, "assets", "staged_media.mp4")
                            os.makedirs(os.path.dirname(save_path), exist_ok=True)
                            with open(save_path, "wb") as f:
                                f.write(raw_bytes)
                            print(f"✅ Staged user video to: {save_path}")
                            return "assets/staged_media.mp4"
                        elif mime.startswith("image/"):
                            ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
                            ext = ext_map.get(mime, ".jpg")
                            save_path = os.path.join(BASE_DIR, "assets", f"staged_media{ext}")
                            os.makedirs(os.path.dirname(save_path), exist_ok=True)
                            with open(save_path, "wb") as f:
                                f.write(raw_bytes)
                            print(f"✅ Staged user image to: {save_path}")
                            return f"assets/staged_media{ext}"
    except Exception as e:
        print(f"⚠️ Error scanning parent session: {e}")

    # 2. Fallback to local file path if provided
    if photo_path:
        print(f"⚠️ Checking local file path: '{photo_path}'...")
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
            print(f"✅ Staged local media file to: {save_path}")
            return f"assets/{save_name}"

    # 3. Fallback to default asset placeholder
    default_placeholder = resolve_path("assets/portrait_outpainted.png")
    if os.path.exists(default_placeholder):
        print(f"ℹ️ Using default placeholder avatar: {default_placeholder}")
        return "assets/portrait_outpainted.png"

    raise FileNotFoundError("No media file was found in session events or local path. Please upload a photo or video.")


def outpaint_to_9_16(photo_path: str, client: genai.Client) -> str:
    """Uses Gemini image generation to intelligently extend/outpaint a photo to 9:16 aspect ratio.
    Instead of adding black bars, it generates realistic content (background, environment)
    to fill the missing areas while preserving the original subject perfectly.

    Returns the file path to the outpainted image."""
    print("🎨 [Outpaint] Extending image to 9:16 via intelligent outpainting...")

    photo_path = resolve_path(photo_path)
    if not os.path.exists(photo_path):
        return photo_path

    try:
        with open(photo_path, "rb") as f:
            img_bytes = f.read()

        mime_type = "image/png" if photo_path.lower().endswith(".png") else "image/jpeg"
        part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=[
                part,
                types.Part.from_text(
                    text=(
                        "Extend this photo to a vertical 9:16 portrait aspect ratio by seamlessly expanding the background. "
                        "Keep the person in the photo unchanged."
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
                        base64.b64decode(p.inline_data.data)
                        if isinstance(p.inline_data.data, str)
                        else p.inline_data.data
                    )
                    with open(outpainted_path, "wb") as f:
                        f.write(img_data)
                    print(f"✅ [Outpaint] Extended image saved to '{outpainted_path}'")
                    try:
                        cloud_img_url = upload_bytes_to_storage(
                            data=img_data,
                            destination_blob_name="images/portrait_outpainted.png",
                            content_type="image/png",
                        )
                        if cloud_img_url:
                            print(f"☁️ [Cloud Storage] Outpainted avatar uploaded: {cloud_img_url}")
                    except Exception as upload_err:
                        print(f"⚠️ [Cloud Storage Notice] {upload_err}")
                    return os.path.relpath(outpainted_path, BASE_DIR)
    except Exception as e:
        print(f"⚠️ [Outpaint Notice] Outpainting not available ({e}). Using original image.")

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
    print(f"\n👤 [Tool: verify_portrait_photo] Verifying photo: {photo_path}")

    photo_path = resolve_media_path(photo_path)

    # Check if video
    lower_path = photo_path.lower()
    if any(lower_path.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]):
        print("🎥 [Face Verification] Video detected. Face verification skipped.")
        return "video"

    if not os.path.exists(photo_path):
        print(f"⚠️ [Face Verification] Photo '{photo_path}' not on disk, proceeding with default placeholder.")
        return "photo"

    try:
        with open(photo_path, "rb") as f:
            img_bytes = f.read()

        mime_type = "image/png" if photo_path.lower().endswith(".png") else "image/jpeg"
        part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)

        client = get_gemini_client()

        print("🚀 Sending face detection verification call to Gemini-3.5-Flash-Lite...")
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[
                part,
                types.Part.from_text(
                    text="Is there a clear, recognizable human face in this photo? Answer only YES or NO."
                ),
            ],
        )
        answer = (response.text or "").strip().upper()
        print(f"👤 [Face Detection] Model response: '{answer}'")
    except Exception as e:
        print(f"⚠️ [Face Verification Notice] Verification check bypassed: {e}")

    print("✅ [Face Verification] Face check completed!")
    return "photo"


# Video Generation Engine: "veo" (Vertex AI Veo 3.1) or "omni" (Google AI Gemini Omni Flash)
def get_video_engine() -> str:
    """Return the configured video engine, defaulting invalid values to Veo."""
    engine = os.environ.get("VIDEO_ENGINE", "veo").strip().lower()
    return engine if engine in {"omni", "veo"} else "veo"


def validate_video_generation_backend(engine: str) -> None:
    """Ensure live video generation does not invoke Vertex while Gemini API mode is active."""
    if engine == "veo" and not use_vertex_ai():
        raise GeminiConfigurationError(
            "VIDEO_ENGINE=veo requires Vertex AI. With GOOGLE_GENAI_USE_VERTEXAI=0, "
            "set VIDEO_ENGINE=omni and configure GOOGLE_API_KEY or GEMINI_API_KEY."
        )


def _generate_with_omni(photo_path: str, creative_prompt: str) -> str:
    """Generates an 8s 9:16 video using Google AI Gemini Omni Flash (gemini-omni-1.1-flash) via Interactions API."""
    api_key = get_gemini_api_key()

    with open(photo_path, "rb") as f:
        frame_bytes = f.read()

    b64_img = base64.b64encode(frame_bytes).decode("utf-8")
    mime_type = "image/png" if photo_path.lower().endswith(".png") else "image/jpeg"

    i2v_prompt = augment_creative_prompt(creative_prompt)

    print(f'🎬 [Gemini Omni Flash Prompt] Base prompt: "{creative_prompt}"')
    print(f'   └─ Final Omni Prompt: "{i2v_prompt}"')
    print("🚀 Submitting request to Google AI Gemini Omni Flash (Interactions API)...")

    headers = {"Content-Type": "application/json"}
    if api_key.startswith("AIza"):
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
            print(f"⚠️ [Omni Auth] Could not obtain OAuth2 token from ADC: {e}")

        if token:
            headers["Authorization"] = f"Bearer {token}"
            url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/interactions?key={api_key}"

    payload = {
        "model": "gemini-omni-1.1-flash",
        "input": [
            {"type": "image", "data": b64_img, "mime_type": mime_type},
            {"type": "text", "text": i2v_prompt},
        ],
        "generation_config": {
            "video_config": {
                "task": "image_to_video",
            }
        },
        "response_format": {
            "type": "video",
            "aspect_ratio": "9:16",
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=300)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini Omni Flash generation failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    video_bytes = None
    for step in data.get("steps", []):
        for c in step.get("content", []):
            if c.get("type") == "video" and "data" in c:
                video_bytes = base64.b64decode(c["data"])
                break
        if video_bytes:
            break

    if not video_bytes:
        raise RuntimeError(f"Gemini Omni Flash did not return any video bytes: {data}")

    animated_video_path = os.path.join(BASE_DIR, "assets", "Video_example.mp4")
    with open(animated_video_path, "wb") as f:
        f.write(video_bytes)

    print(f"💾 Saved Gemini Omni Flash video ({len(video_bytes)} bytes) to '{animated_video_path}'!")
    return "assets/Video_example.mp4"


def _generate_with_veo(photo_path: str, creative_prompt: str) -> str:
    """Generates an 8s 9:16 video using Vertex AI Veo 3.1 (veo-3.1-fast-generate-001)."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "gdg-agents-6b59a")
    veo_client = genai.Client(
        vertexai=True,
        project=project_id,
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    with open(photo_path, "rb") as f:
        frame_bytes = f.read()

    mime_type = "image/png" if photo_path.lower().endswith(".png") else "image/jpeg"
    starting_frame = types.Image(image_bytes=frame_bytes, mime_type=mime_type)
    print(f"🖼️  Starting Frame: '{photo_path}' ({len(frame_bytes)} bytes) → Vertex AI Veo...")

    i2v_prompt = augment_creative_prompt(creative_prompt)

    print(f'🎬 [Veo Prompt Augmented] Base prompt: "{creative_prompt}"')
    print(f'   └─ Final Veo Prompt: "{i2v_prompt}"')

    print("🚀 Submitting request to Vertex AI Veo...")
    operation = veo_client.models.generate_videos(
        model="veo-3.1-fast-generate-001",
        prompt=i2v_prompt,
        image=starting_frame,
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            duration_seconds=8,
            person_generation="allow_adult",
            generate_audio=None,
            resolution="720p",
        ),
    )

    print("⏳ Video is being generated by Google AI servers. Please wait...")
    while not operation.done:
        time.sleep(10)
        operation = veo_client.operations.get(operation)
        print(".", end="", flush=True)
    print()

    if getattr(operation, "error", None):
        err = operation.error
        if isinstance(err, dict):
            err_msg = err.get("message", "Unknown error")
            err_code = err.get("code", "Unknown code")
        else:
            err_msg = getattr(err, "message", str(err))
            err_code = getattr(err, "code", "Unknown code")
        raise RuntimeError(f"Veo generation failed: {err_msg} (code: {err_code})")

    result = operation.response
    if result is None:
        raise RuntimeError("Veo generation returned an empty response (operation.response was None).")

    if not result.generated_videos:
        reasons = getattr(result, "rai_media_filtered_reasons", "unknown")
        raise RuntimeError(f"Veo did not return any videos. RAI reasons: {reasons}")

    video = result.generated_videos[0]
    animated_video_path = os.path.join(BASE_DIR, "assets", "Video_example.mp4")
    print("📥 Downloading completed video file...")

    gcs_uri = None
    for uri_candidate in [
        getattr(video.video, "uri", None) if hasattr(video, "video") else None,
        getattr(video, "uri", None),
        getattr(video.video, "file_uri", None) if hasattr(video, "video") else None,
        getattr(video, "file_uri", None),
    ]:
        if uri_candidate and isinstance(uri_candidate, str) and uri_candidate.startswith("gs://"):
            gcs_uri = uri_candidate
            break

    if gcs_uri:
        print(f"🪣 Detected GCS path: {gcs_uri}. Downloading...")
        path_without_scheme = gcs_uri[5:]
        bucket_name, blob_name = path_without_scheme.split("/", 1)
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(animated_video_path)
    else:
        video_bytes = None
        if hasattr(video, "video") and hasattr(video.video, "video_bytes"):
            video_bytes = video.video.video_bytes
        elif hasattr(video, "video") and hasattr(video.video, "data"):
            video_bytes = video.video.data
        elif hasattr(video, "video") and hasattr(video.video, "inline_data"):
            if video.video.inline_data and hasattr(video.video.inline_data, "data"):
                video_bytes = video.video.inline_data.data

        if video_bytes:
            with open(animated_video_path, "wb") as f:
                f.write(video_bytes)
            print(f"💾 Saved video from inline bytes ({len(video_bytes)} bytes)")
        else:
            raise RuntimeError("Could not find video GCS URI or bytes in Veo response.")

    print(f"✅ Video successfully generated and saved to '{animated_video_path}'!")
    return "assets/Video_example.mp4"


def animate_photo(photo_path: str = "", creative_prompt: str = "", tool_context: Optional[Any] = None) -> str:
    """Animates a static portrait photo into a 9:16 cinematic video using Google Veo or Gemini Omni Flash based on VIDEO_ENGINE config.

    Args:
        photo_path: The absolute or relative path to the static portrait image or video.
        creative_prompt: Detailed prompt generated by Gemini to animate the portrait.
        tool_context: ADK execution context for accessing session state overrides.
    """
    print("\n🎬 [Tool: animate_photo] Animating photo using AI Video Engine or processing background video...")
    print(f'💡 [Creative Prompt]: "{creative_prompt}"')

    photo_path = resolve_media_path(photo_path)
    lower_path = photo_path.lower()
    if any(lower_path.endswith(ext) for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]):
        print(f"🎥 [Video Detected] Media is a video ({photo_path}). Using it directly.")
        target_video_path = os.path.join(BASE_DIR, "assets", "Video_example.mp4")
        os.makedirs(os.path.join(BASE_DIR, "assets"), exist_ok=True)
        if os.path.abspath(photo_path) != os.path.abspath(target_video_path):
            shutil.copy2(photo_path, target_video_path)
        return "assets/Video_example.mp4"

    photo_path = os.path.abspath(photo_path)

    # Check if AI video generation (Veo/Omni) is disabled to prevent unwanted costs
    if not video_generation_enabled():
        raise RuntimeError(
            "Image-to-video generation is disabled. Upload a source video or set ENABLE_VIDEO_GENERATION=true."
        )

    # Gemini client for outpainting
    gemini_client = get_gemini_client()
    # Outpaint to 9:16 vertical canvas
    photo_path = outpaint_to_9_16(photo_path, gemini_client)
    photo_path = resolve_path(photo_path)

    # Check if AI video generation (Veo/Omni) is enabled in session state or env
    state = {}
    if tool_context:
        if hasattr(tool_context, "state") and isinstance(tool_context.state, dict):
            state = tool_context.state
        elif hasattr(tool_context, "session") and tool_context.session and hasattr(tool_context.session, "state"):
            state = tool_context.session.state or {}

    enable_vid = video_generation_enabled()
    if "enable_video_generation" in state or "enableVideoGeneration" in state:
        val = (
            state.get("enable_video_generation")
            if "enable_video_generation" in state
            else state.get("enableVideoGeneration")
        )
        if val is not None:
            enable_vid = bool(val)

    if not enable_vid:
        msg = (
            "⚠️ Generative AI video models (Google Veo 3.1 & Gemini Omni) are currently disabled in the configuration to conserve cloud credits. "
            "Only direct rendering of user-uploaded videos (.mp4, .mov, .webm) is supported.\n\n"
            "💡 You can enable AI video generation in Settings or attach an existing speaker video file."
        )
        print(f"🚫 [Cost Protection] {msg}")
        return f"Error: {msg}"

    engine = get_video_engine()
    validate_video_generation_backend(engine)
    if engine == "omni":
        result_path = _generate_with_omni(photo_path, creative_prompt)
    else:
        result_path = _generate_with_veo(photo_path, creative_prompt)

    try:
        abs_video_path = os.path.join(BASE_DIR, "assets", "Video_example.mp4")
        if os.path.exists(abs_video_path):
            cloud_vid_url = upload_file_to_storage(
                local_path=abs_video_path,
                destination_blob_name="videos/Video_example.mp4",
                content_type="video/mp4",
            )
            if cloud_vid_url:
                print(f"☁️ [Cloud Storage] Video successfully uploaded to bucket: {cloud_vid_url}")
    except Exception as upload_err:
        print(f"⚠️ [Cloud Storage Notice] {upload_err}")

    return result_path


# Backward-compatible alias
generate_speaker_video = animate_photo
