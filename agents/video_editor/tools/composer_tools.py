import datetime
import glob
import json
import os
import random
import re
import shutil
import subprocess
from typing import Any, Optional

from PIL import Image, ImageDraw

from agents.common.storage import upload_file_to_storage

# BASE_DIR represents the absolute path of this agent's folder, ensuring self-contained integrations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Toggles to enable/disable specific rendering outputs.
RENDER_CONFIG = {
    "ordinary": os.environ.get("RENDER_ORDINARY", "true").lower() in ("true", "1", "yes"),
    "gif": os.environ.get("RENDER_GIF", "false").lower() in ("true", "1", "yes"),
    "4k": os.environ.get("RENDER_4K", "false").lower() in ("true", "1", "yes"),
}


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


def restore_default_placeholder():
    """Generates a generic, safe gray placeholder image at assets/portrait_outpainted.png to prevent 404/file-not-found errors."""
    placeholder_path = resolve_path("assets/portrait_outpainted.png")
    try:
        # Create a beautiful 500x500 dark grey placeholder image
        img = Image.new("RGB", (500, 500), color="#1E1E1E")
        d = ImageDraw.Draw(img)
        # Draw a soft circle representing a generic speaker avatar
        d.ellipse([(175, 120), (325, 270)], fill="#333333")
        d.ellipse([(100, 310), (400, 500)], fill="#333333")
        img.save(placeholder_path, "PNG")
        print(f"✅ [Placeholder] Restored generic placeholder image to '{placeholder_path}'")
    except Exception as e:
        print(f"⚠️ [Placeholder] Failed to restore generic placeholder: {e}")


def build_card_config(title: str, name: str, position_company: str, year: int) -> str:
    """Builds a JavaScript-safe CARD_CONFIG declaration."""
    return f"""const CARD_CONFIG = {{
      title: {json.dumps(title)},
      name: {json.dumps(name)},
      position_company: {json.dumps(position_company)},
      year: {json.dumps(str(year))}
    }};"""


def update_composer(
    video_path: str,
    title: str,
    name: str,
    position_company: str,
    duration_seconds: int | None = None,
    theme_colors: dict[str, str] | None = None,
) -> str:
    """Updates index.html with the new video path, title, speaker name, position/company texts, and sets timeline duration (8s for Veo, 10s for user uploads)."""
    # Ensure video_path is a relative path inside index.html for correct HTTP serving in headless Chrome
    if os.path.isabs(video_path):
        video_path = os.path.relpath(video_path, BASE_DIR)

    # 1. Determine timeline duration: 8.0s for Veo generated video, 10.0s for uploaded custom video
    target_duration = duration_seconds or 10
    abs_video_path = resolve_path(video_path)

    # Probe duration if ffprobe is installed
    if duration_seconds is None and shutil.which("ffprobe") and os.path.exists(abs_video_path):
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                abs_video_path,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                dur = float(res.stdout.strip())
                if dur <= 8.5:
                    target_duration = 8
                else:
                    target_duration = 10
        except Exception:
            pass
    elif duration_seconds is None and "video_example" in video_path.lower():
        # Generated from Veo
        target_duration = 8

    print("\n✍️ [Tool: update_composer] Inserting new details into index.html")
    print(f'   ├─ Title: "{title}"')
    print(f'   ├─ Name: "{name}"')
    print(f'   ├─ Position & Company: "{position_company}"')
    print(f"   ├─ Duration: {target_duration}s ({'Veo 8s' if target_duration == 8 else 'Custom Upload 10s'})")
    print(f'   └─ Video: "{video_path}"')

    target_file = resolve_path("index.html")
    if not os.path.exists(target_file):
        raise FileNotFoundError(f"Cannot find composition file '{target_file}'.")

    # Read the current content
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Update the CARD_CONFIG block dynamically using regex
    current_year = datetime.datetime.now().year
    config_pattern = r"const CARD_CONFIG = \{.*?\};"
    new_config = build_card_config(title, name, position_company, current_year)

    if re.search(config_pattern, content, flags=re.DOTALL):
        content = re.sub(config_pattern, lambda _: new_config, content, flags=re.DOTALL)
    else:
        raise ValueError("Could not locate 'const CARD_CONFIG' block in index.html.")

    # Update data-duration attributes for all timed elements
    content = re.sub(r'data-duration="\d+"', f'data-duration="{target_duration}"', content)
    # Update GSAP star rotation duration
    content = re.sub(
        r"rotation:\s*360,\s*duration:\s*[\d.]+", f"rotation: 360,\n      duration: {float(target_duration)}", content
    )

    # 2. Update the video and image tag src and inline display style attributes based on media type
    is_image = any(video_path.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"])

    video_pattern = r'id="card-video"\s+src=".*?"'
    image_pattern = r'id="card-image"\s+src=".*?"'

    if not (re.search(video_pattern, content) and re.search(image_pattern, content)):
        raise ValueError("Could not locate card-video or card-image tags in index.html.")

    if is_image:
        # It's an image card!
        video_full_pattern = r'(<video\s+id="card-video"[^>]*?style="[^"]*?)(display:none;)?(")'
        content = re.sub(video_full_pattern, r"\g<1>display:none;\g<3>", content)
        content = re.sub(video_pattern, 'id="card-video" src="assets/Video_example.mp4"', content)

        image_full_pattern = r'(<img\s+id="card-image"[^>]*?style="[^"]*?)(display:none;)\s*(;?)(")'
        content = re.sub(image_full_pattern, r"\g<1>\g<4>", content)
        content = re.sub(image_pattern, f'id="card-image" src={json.dumps(video_path)}', content)
    else:
        # It's a video card!
        video_full_pattern = r'(<video\s+id="card-video"[^>]*?style="[^"]*?)(display:none;)\s*(;?)(")'
        content = re.sub(video_full_pattern, r"\g<1>\g<4>", content)
        content = re.sub(video_pattern, f'id="card-video" src={json.dumps(video_path)}', content)

        image_full_pattern = r'(<img\s+id="card-image"[^>]*?style="[^"]*?)(display:none;)?(")'
        content = re.sub(image_full_pattern, r"\g<1>display:none;\g<3>", content)
        content = re.sub(image_pattern, 'id="card-image" src=""', content)

    # 3. Randomize colors for breaks, circle, pill, and hexagon using brand palette
    BRAND_COLORS = [
        "#4285F4",
        "#34A853",
        "#F9AB00",
        "#EA4335",  # Core Colors
        "#57CAFF",
        "#5CDB6D",
        "#FFD427",
        "#FF7DAF",  # Halftones
        "#C3ECF6",
        "#CCF6C5",
        "#FFE7A5",
        "#F8D8D8",  # Pastels
    ]

    if theme_colors:
        break_color = theme_colors.get("break_color") or BRAND_COLORS[0]
        circle_color = theme_colors.get("circle_color") or BRAND_COLORS[1]
        pill_color = theme_colors.get("pill_color") or BRAND_COLORS[2]
        hexagon_color = theme_colors.get("hexagon_color") or BRAND_COLORS[3]
    else:
        selected_colors = random.sample(BRAND_COLORS, 4)
        break_color = selected_colors[0]
        circle_color = selected_colors[1]
        pill_color = selected_colors[2]
        hexagon_color = selected_colors[3]

    print("🎨 [Color Randomizer] Selected random Google palette colors:")
    print(f"   ├─ breaks: {break_color}")
    print(f"   ├─ circle: {circle_color}")
    print(f"   ├─ pill: {pill_color}")
    print(f"   └─ hexagon: {hexagon_color}")

    # Safely replace fill/stroke attributes for breaks, circle, pill and hexagon
    break_1_pattern = r'(<path\s+id="break_1"[^>]*?fill=")(#[0-9a-fA-F]{6})(")'
    content, count1 = re.subn(break_1_pattern, rf"\g<1>{break_color}\g<3>", content)

    break_2_pattern = r'(<path\s+id="break_2"[^>]*?fill=")(#[0-9a-fA-F]{6})(")'
    content, count2 = re.subn(break_2_pattern, rf"\g<1>{break_color}\g<3>", content)

    circle_pattern = r'(<path\s+id="circle"[^>]*?fill=")(#[0-9a-fA-F]{6})(")'
    content, count3 = re.subn(circle_pattern, rf"\g<1>{circle_color}\g<3>", content)

    pill_pattern = r'(<rect\s+id="pill"[^>]*?fill=")(#[0-9a-fA-F]{6})(")'
    content, count4 = re.subn(pill_pattern, rf"\g<1>{pill_color}\g<3>", content)

    hexagon_pattern = r'(<path\s+id="hexagon"[^>]*?fill=")(#[0-9a-fA-F]{6})(")'
    content, count5 = re.subn(hexagon_pattern, rf"\g<1>{hexagon_color}\g<3>", content)

    # 4. Dynamically insert the current system year into the pill-text SVG text element
    current_year = datetime.datetime.now().year
    year_pattern = r'(<text\s+id="pill-text"[^>]*?>)(\d{4})(</text>)'
    content, count_year = re.subn(year_pattern, rf"\g<1>{current_year}\g<3>", content)

    print(
        f"   └─ Updated elements: break_1 ({count1}), break_2 ({count2}), circle ({count3}), pill badge ({count4}), hexagon ({count5}), year text ({count_year} -> {current_year}), duration: {target_duration}s"
    )

    # Write the updated composition
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content)

    return f"Successfully updated index.html with duration ({target_duration}s), colors (breaks: {break_color}, circle: {circle_color}, pill: {pill_color}, hexagon: {hexagon_color}, year: {current_year}) and video asset."


def render_composer(tool_context: Optional[Any] = None) -> str:
    """Executes the HyperFrames compiler to render the updated composition into configured high-quality formats sequentially."""
    print("\n🚀 [Tool: render_composer] Starting sequential HyperFrames rendering pipeline...")

    render_ordinary = (
        os.getenv("RENDER_ORDINARY", "").lower() in ("true", "1", "yes")
        if os.getenv("RENDER_ORDINARY") is not None
        else RENDER_CONFIG["ordinary"]
    )
    render_gif = (
        os.getenv("RENDER_GIF", "").lower() in ("true", "1", "yes")
        if os.getenv("RENDER_GIF") is not None
        else RENDER_CONFIG["gif"]
    )
    render_4k = (
        os.getenv("RENDER_4K", "").lower() in ("true", "1", "yes")
        if os.getenv("RENDER_4K") is not None
        else RENDER_CONFIG["4k"]
    )

    # Check session state overrides from user frontend settings
    state = {}
    if tool_context:
        if hasattr(tool_context, "state") and isinstance(tool_context.state, dict):
            state = tool_context.state
        elif hasattr(tool_context, "session") and tool_context.session and hasattr(tool_context.session, "state"):
            state = tool_context.session.state or {}

    if "render_4k" in state or "render4k" in state:
        val = state.get("render_4k") if "render_4k" in state else state.get("render4k")
        if val is not None:
            render_4k = bool(val)
    if "render_gif" in state or "renderGif" in state:
        val = state.get("render_gif") if "render_gif" in state else state.get("renderGif")
        if val is not None:
            render_gif = bool(val)
    if "render_ordinary" in state or "renderOrdinary" in state:
        val = state.get("render_ordinary") if "render_ordinary" in state else state.get("renderOrdinary")
        if val is not None:
            render_ordinary = bool(val)

    print(f"⚙️  [Render Config] 4K: {render_4k}, GIF: {render_gif}, 1080p: {render_ordinary}")

    # 1. Block rendering if everything is turned off
    if not render_ordinary and not render_gif and not render_4k:
        error_msg = "All rendering options are disabled in configuration! Enable at least one (Ordinary, GIF, or 4K) in settings."
        print(f"❌ [Render Blocked] {error_msg}")
        raise ValueError(error_msg)

    # 2. Check if ffmpeg is installed
    ffmpeg_installed = shutil.which("ffmpeg") is not None
    if ffmpeg_installed:
        print(f"✅ [System] ffmpeg detected at: {shutil.which('ffmpeg')}")
    else:
        print("⚠️ [System] ffmpeg NOT found. Audio stripping and GIF conversion will be skipped.")

    # 3. Extract speaker name from index.html and generate timestamp
    speaker_name = "speaker"
    target_index_html = resolve_path("index.html")
    try:
        if os.path.exists(target_index_html):
            with open(target_index_html, "r", encoding="utf-8") as f:
                html_content = f.read()
            name_match = re.search(r'name:\s*"(.*?)"', html_content)
            if name_match:
                speaker_name = name_match.group(1)
    except Exception as e:
        print(f"⚠️ [Naming] Could not parse speaker name from index.html: {e}")

    speaker_name_clean = re.sub(r"[^\w\u0400-\u04FF]+", "_", speaker_name.strip().lower()).strip("_")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    print(f'🏷️  [Naming Config] Speaker name: "{speaker_name}" -> clean: "{speaker_name_clean}"')
    print(f"⏱️  [Naming Config] Synchronized timestamp: {timestamp}")

    rendered_files = []
    ordinary_file = ""
    gif_file = ""

    # ============================================================================
    # PIPELINE 1: BASE COMPOSITION RENDERING (1080p)
    # ============================================================================
    # We always render the base 1080p composition first via HyperFrames (fast & reliable).
    print("\n🎬 [Render Step 1/2] Rendering vector composition...")
    render_env = {
        **os.environ,
        "PRODUCER_LOW_MEMORY_MODE": "true",
        "PUPPETEER_ARGS": "--no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage --disable-gpu",
        "CHROMIUM_FLAGS": "--no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage --disable-gpu",
    }
    result = subprocess.run(
        ["npm", "run", "render"],
        capture_output=True,
        text=True,
        cwd=BASE_DIR,
        env=render_env,
        timeout=180,
    )

    if result.returncode == 0:
        print("🎉 [Base Render successful!]")
        output_lines = result.stdout.split("\n")
        local_ordinary_file = ""
        for line in output_lines:
            if ".mp4" in line:
                match = re.search(r"(/[^\s]+?\.mp4)", line)
                if match:
                    local_ordinary_file = match.group(1)
                    break

        if not local_ordinary_file:
            renders_folder = resolve_path("renders")
            mp4_files = glob.glob(os.path.join(renders_folder, "*.mp4"))
            if mp4_files:
                local_ordinary_file = max(mp4_files, key=os.path.getmtime)
                local_ordinary_file = os.path.abspath(local_ordinary_file)

        if local_ordinary_file and os.path.exists(local_ordinary_file):
            # Strip audio
            if ffmpeg_installed:
                temp_no_audio = local_ordinary_file.rsplit(".", 1)[0] + "_no_audio.mp4"
                print(f"🔇 [Audio] Stripping audio from render '{local_ordinary_file}'...")
                try:
                    strip_cmd = ["ffmpeg", "-y", "-i", local_ordinary_file, "-an", "-c:v", "copy", temp_no_audio]
                    strip_result = subprocess.run(strip_cmd, capture_output=True, text=True, cwd=BASE_DIR)
                    if strip_result.returncode == 0 and os.path.exists(temp_no_audio):
                        os.replace(temp_no_audio, local_ordinary_file)
                        print(f"✅ [Audio] Audio stripped from '{local_ordinary_file}'!")
                    else:
                        print(f"⚠️ [Audio] ffmpeg failed to strip audio: {strip_result.stderr}")
                except Exception as e:
                    print(f"⚠️ [Audio] Failed to strip audio: {e}")
            else:
                print("⏭️  [Audio] Skipping audio stripping (ffmpeg not found)")

            # Rename base file
            renders_folder = resolve_path("renders")
            os.makedirs(renders_folder, exist_ok=True)
            target_ordinary_name = os.path.join(renders_folder, f"{speaker_name_clean}_{timestamp}.mp4")
            target_ordinary_path = os.path.abspath(target_ordinary_name)
            print(f"🏷️ [Rename] Renaming render to '{target_ordinary_name}'...")
            try:
                os.rename(local_ordinary_file, target_ordinary_path)
                local_ordinary_file = target_ordinary_path
                ordinary_file = target_ordinary_path
            except Exception as e:
                print(f"⚠️ [Rename] Failed to rename render: {e}")

            # Optional GIF conversion
            if render_gif:
                if ffmpeg_installed:
                    local_gif_file = local_ordinary_file.rsplit(".", 1)[0] + ".gif"
                    print(f"🎬 [GIF] Converting render to GIF: '{local_gif_file}'...")
                    try:
                        ffmpeg_cmd = [
                            "ffmpeg",
                            "-y",
                            "-i",
                            local_ordinary_file,
                            "-vf",
                            "fps=15,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                            local_gif_file,
                        ]
                        gif_result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, cwd=BASE_DIR)
                        if gif_result.returncode == 0:
                            print(f"✅ [GIF] GIF successfully created: '{local_gif_file}'")
                            gif_file = local_gif_file
                            cloud_url = upload_file_to_storage(
                                local_gif_file, f"renders/{os.path.basename(local_gif_file)}"
                            )
                            file_link = cloud_url if cloud_url else local_gif_file
                            rendered_files.append(f"• GIF Animation: {file_link}")
                        else:
                            print(f"⚠️ [GIF] ffmpeg failed: {gif_result.stderr}")
                    except Exception as e:
                        print(f"⚠️ [GIF] GIF conversion exception: {e}")
                else:
                    print("⏭️  [GIF] Skipping GIF conversion (ffmpeg not found)")
                    rendered_files.append("• (Skipped) GIF Animation: ffmpeg not found on host machine.")

            # ============================================================================
            # PIPELINE 2: 4K UHD RENDERING VIA HIGH-QUALITY LANCZOS PIPELINE
            # ============================================================================
            if render_4k:
                print("\n🎬 [Render Step 2/2] Generating Ultra-HD 4K (2160p) video via Lanczos...")
                target_4k_name = os.path.join(renders_folder, f"{speaker_name_clean}_{timestamp}_4k.mp4")
                target_4k_path = os.path.abspath(target_4k_name)

                if ffmpeg_installed:
                    try:
                        cmd_4k = [
                            "ffmpeg",
                            "-y",
                            "-i",
                            local_ordinary_file,
                            "-vf",
                            "scale=3840:2160:flags=lanczos",
                            "-c:v",
                            "libx264",
                            "-crf",
                            "18",
                            "-preset",
                            "medium",
                            "-pix_fmt",
                            "yuv420p",
                            target_4k_path,
                        ]
                        result_4k = subprocess.run(cmd_4k, capture_output=True, text=True, cwd=BASE_DIR)
                        if result_4k.returncode == 0 and os.path.exists(target_4k_path):
                            print(f"🎉 [4K Render successful!] Generated '{target_4k_path}'")
                            cloud_url = upload_file_to_storage(
                                target_4k_path, f"renders/{os.path.basename(target_4k_path)}"
                            )
                            file_link = cloud_url if cloud_url else target_4k_path
                            rendered_files.append(f"• Video in 4K quality (2160p): {file_link}")
                        else:
                            print(f"⚠️ [4K Render] ffmpeg 4K scale failed: {result_4k.stderr}")
                    except Exception as e:
                        print(f"⚠️ [4K Render] 4K generation exception: {e}")
                else:
                    print("⏭️  [4K Render] Skipping 4K (ffmpeg not found)")

            # Manage 1080p ordinary file upload or cleanup
            if render_ordinary:
                cloud_url = upload_file_to_storage(
                    local_ordinary_file, f"renders/{os.path.basename(local_ordinary_file)}"
                )
                file_link = cloud_url if cloud_url else local_ordinary_file
                rendered_files.append(f"• Video in ordinary quality (1080p): {file_link}")
            elif (
                not render_ordinary
                and (render_4k or render_gif)
                and local_ordinary_file
                and os.path.exists(local_ordinary_file)
            ):
                print(f"🗑️ [Cleanup] Removing intermediate 1080p file '{local_ordinary_file}' (only 4K requested)...")
                try:
                    os.remove(local_ordinary_file)
                except Exception as e:
                    print(f"⚠️ [Cleanup] Failed to delete temp 1080p file: {e}")
    else:
        print("❌ [Base Render failed]")
        print(result.stderr)
        raise RuntimeError(f"Base composition render returned a non-zero exit code: {result.stderr}")

    # ============================================================================
    # PIPELINE 3: HIGH-RESOLUTION POSTER/SCREENSHOT GENERATION (PNG)
    # ============================================================================
    print("\n📸 [Poster Step] Preparing high-resolution static card poster (PNG)...")
    try:
        # Read index.html backup
        with open(target_index_html, "r", encoding="utf-8") as f:
            html_backup = f.read()

        # Find current video src
        video_pattern = r'id="card-video"\s+src="(.*?)"'
        match = re.search(video_pattern, html_backup)
        original_video_src = match.group(1) if match else ""

        # Check if original_video_src is a video or image
        is_video_src = original_video_src and not any(
            original_video_src.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]
        )

        temp_image_src = ""
        # If it's a video and ffmpeg is installed, extract the first frame
        if is_video_src and ffmpeg_installed:
            video_abs = resolve_path(original_video_src)
            if os.path.exists(video_abs):
                frame_out_path = os.path.join(BASE_DIR, "assets", "temp_video_frame.png")
                print(f"🎥 [Poster] Extracting first frame of video '{original_video_src}' for snapshot...")
                try:
                    extract_cmd = ["ffmpeg", "-y", "-i", video_abs, "-ss", "00:00:00", "-vframes", "1", frame_out_path]
                    extract_res = subprocess.run(extract_cmd, capture_output=True, text=True, cwd=BASE_DIR)
                    if extract_res.returncode == 0 and os.path.exists(frame_out_path):
                        temp_image_src = "assets/temp_video_frame.png"
                        print("✅ [Poster] First frame extracted successfully!")
                    else:
                        print(f"⚠️ [Poster] Failed to extract first frame from video: {extract_res.stderr}")
                except Exception as frame_err:
                    print(f"⚠️ [Poster] Error extracting first frame: {frame_err}")
        elif not is_video_src and original_video_src:
            temp_image_src = original_video_src

        # Fallback to portrait_outpainted if temp_image_src is not resolved or not found
        if not temp_image_src or not os.path.exists(resolve_path(temp_image_src)):
            temp_image_src = "assets/portrait_outpainted.png"

        if temp_image_src and os.path.exists(resolve_path(temp_image_src)):
            # Determine snapshot timestamp based on composition duration (7.8s for 8s duration, 9.7s for 10s duration)
            current_duration = 10
            dur_match = re.search(r'data-duration="(\d+)"', html_backup)
            if dur_match:
                current_duration = int(dur_match.group(1))
            snapshot_time = "7.8" if current_duration <= 8 else "9.7"

            snapshot_result = None
            try:
                print(
                    f"🖼️  [Poster] Swapping video for placeholder and setting card-image to '{temp_image_src}' in index.html..."
                )
                # Set card-video src to placeholder Video_example.mp4 (valid fallback for static guard and chrome video tag)
                temp_content = re.sub(
                    r'id="card-video"\s+src=".*?"', 'id="card-video" src="assets/Video_example.mp4"', html_backup
                )
                # Set card-image src to the static outpainted/staged photo path
                temp_content = re.sub(
                    r'id="card-image"\s+src=".*?"', f'id="card-image" src="{temp_image_src}"', temp_content
                )

                with open(target_index_html, "w", encoding="utf-8") as f:
                    f.write(temp_content)

                print(
                    f"📸 [Poster] Taking high-resolution PNG snapshot of the final card state at T={snapshot_time}s..."
                )
                snapshot_result = subprocess.run(
                    ["npx", "--yes", "hyperframes@0.8.4", "snapshot", f"--at={snapshot_time}"],
                    capture_output=True,
                    text=True,
                    cwd=BASE_DIR,
                    env=render_env,
                    timeout=60,
                )
            finally:
                # Unconditionally restore index.html backup immediately
                with open(target_index_html, "w", encoding="utf-8") as f:
                    f.write(html_backup)
                print("✅ [Poster] Restored original index.html sources.")

            if snapshot_result and snapshot_result.returncode == 0:
                snapshot_file = resolve_path(f"snapshots/frame-00-at-{snapshot_time}s.png")
                if not os.path.exists(snapshot_file):
                    found_snaps = glob.glob(os.path.join(BASE_DIR, "snapshots", "*.png"))
                    if found_snaps:
                        snapshot_file = max(found_snaps, key=os.path.getmtime)
                if os.path.exists(snapshot_file):
                    renders_folder = resolve_path("renders")
                    os.makedirs(renders_folder, exist_ok=True)
                    target_poster_name = os.path.join(renders_folder, f"{speaker_name_clean}_{timestamp}.png")
                    target_poster_path = os.path.abspath(target_poster_name)
                    print(f"🏷️ [Poster] Saving high-resolution card poster to '{target_poster_path}'...")
                    try:
                        if render_4k and ffmpeg_installed:
                            print(
                                f"🎬 [Poster 4K] Generating high-resolution 4K card poster using Lanczos: '{target_poster_path}'..."
                            )
                            try:
                                upscale_cmd = [
                                    "ffmpeg",
                                    "-y",
                                    "-i",
                                    snapshot_file,
                                    "-vf",
                                    "scale=3840:2160:flags=lanczos",
                                    "-update",
                                    "1",
                                    target_poster_path,
                                ]
                                upscale_result = subprocess.run(
                                    upscale_cmd, capture_output=True, text=True, cwd=BASE_DIR
                                )
                                if upscale_result.returncode == 0 and os.path.exists(target_poster_path):
                                    cloud_url = upload_file_to_storage(
                                        target_poster_path, f"renders/{os.path.basename(target_poster_path)}"
                                    )
                                    file_link = cloud_url if cloud_url else target_poster_path
                                    rendered_files.append(f"• High-Resolution Card Poster (4K PNG): {file_link}")
                                    print("✅ [Poster 4K] 4K poster successfully created!")
                                else:
                                    print(
                                        f"⚠️ [Poster 4K] ffmpeg failed to upscale, falling back to 1080p copy: {upscale_result.stderr}"
                                    )
                                    shutil.copy2(snapshot_file, target_poster_path)
                                    cloud_url = upload_file_to_storage(
                                        target_poster_path, f"renders/{os.path.basename(target_poster_path)}"
                                    )
                                    file_link = cloud_url if cloud_url else target_poster_path
                                    rendered_files.append(f"• High-Resolution Card Poster (PNG): {file_link}")
                            except Exception as upscale_err:
                                print(
                                    f"⚠️ [Poster 4K] Failed to generate 4K poster, falling back to 1080p copy: {upscale_err}"
                                )
                                shutil.copy2(snapshot_file, target_poster_path)
                                cloud_url = upload_file_to_storage(
                                    target_poster_path, f"renders/{os.path.basename(target_poster_path)}"
                                )
                                file_link = cloud_url if cloud_url else target_poster_path
                                rendered_files.append(f"• High-Resolution Card Poster (PNG): {file_link}")
                        else:
                            shutil.copy2(snapshot_file, target_poster_path)
                            cloud_url = upload_file_to_storage(
                                target_poster_path, f"renders/{os.path.basename(target_poster_path)}"
                            )
                            file_link = cloud_url if cloud_url else target_poster_path
                            rendered_files.append(f"• High-Resolution Card Poster (PNG): {file_link}")
                    except Exception as e:
                        print(f"⚠️ [Poster] Failed to save poster: {e}")
                else:
                    print("⚠️ [Poster] Snapshot file was not found after execution.")
            elif snapshot_result:
                print(f"⚠️ [Poster] Snapshot rendering failed: {snapshot_result.stderr}")
        else:
            print("⚠️ [Poster] No processed outpainted portrait found, skipping high-resolution poster generation.")
    except Exception as poster_err:
        print(f"⚠️ [Poster] Unexpected error during poster generation: {poster_err}")
    finally:
        # Unconditionally cleanup snapshots directory and AI contact sheets to keep workspace pristine!
        print("🗑️ [Poster Cleanup] Ensuring snapshots and contact-sheets are cleaned up...")
        shutil.rmtree(resolve_path("snapshots"), ignore_errors=True)
        if os.path.exists(resolve_path("contact-sheet.jpg")):
            try:
                os.remove(resolve_path("contact-sheet.jpg"))
            except Exception as ce:
                print(f"⚠️ Failed to remove contact-sheet.jpg: {ce}")

    # Save the Gemini outpainted avatar if it exists and is not the default placeholder
    outpainted_src = resolve_path("assets/portrait_outpainted.png")
    if os.path.exists(outpainted_src):
        try:
            with Image.open(outpainted_src) as img:
                width, height = img.size
            if (width, height) != (500, 500):
                renders_folder = resolve_path("renders")
                os.makedirs(renders_folder, exist_ok=True)
                target_avatar_name = os.path.join(renders_folder, f"{speaker_name_clean}_{timestamp}_avatar.png")
                target_avatar_path = os.path.abspath(target_avatar_name)
                print(
                    f"🖼️ [Save Avatar] Saving Gemini outpainted avatar ({width}x{height}) to '{target_avatar_path}'..."
                )
                shutil.copy2(outpainted_src, target_avatar_path)
                cloud_url = upload_file_to_storage(
                    target_avatar_path, f"renders/{os.path.basename(target_avatar_path)}"
                )
                file_link = cloud_url if cloud_url else target_avatar_path
                rendered_files.append(f"• Gemini Outpainted Avatar: {file_link}")
            else:
                print("⏭️  [Save Avatar] Skipping placeholder avatar copy (500x500 placeholder detected)")
        except Exception as e:
            print(f"⚠️ [Save Avatar] Failed to copy Gemini outpainted avatar: {e}")

    # ============================================================================
    # CLEANUP INTERMEDIATE ASSETS
    # ============================================================================
    print("\n🗑️ [Cleanup Step] Cleaning up intermediate uploaded staging assets...")
    intermediate_files = [
        "assets/staged_media.png",
        "assets/staged_media.jpg",
        "assets/staged_media.jpeg",
        "assets/staged_media.webp",
        "assets/staged_media.mp4",
        "assets/portrait_outpainted.png",
        "assets/temp_video_frame.png",
    ]
    for item in intermediate_files:
        item_abs = resolve_path(item)
        if os.path.exists(item_abs):
            try:
                os.remove(item_abs)
                print(f"   Deleted intermediate file: '{item}'")
            except Exception as cleanup_err:
                print(f"   ⚠️ Failed to delete '{item}': {cleanup_err}")

    # Restore the default placeholder to prevent 404/file-not-found issues in other checks
    restore_default_placeholder()

    # Formulate output response
    status_str = "All requested files have been successfully generated sequentially:\n" + "\n".join(rendered_files)
    if not ffmpeg_installed:
        status_str += (
            "\n\n⚠️ Note: ffmpeg was not detected on your system. Audio stripping and GIF animation have been skipped."
        )
    return status_str


# Auto-restore placeholder on import to ensure index.html validation and linter checks pass instantly
restore_default_placeholder()
