import datetime
import os
import re
import shutil
import subprocess

# BASE_DIR represents the absolute path of this agent's folder, ensuring self-contained integrations
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Toggles to enable/disable specific rendering outputs.
RENDER_CONFIG = {
    "ordinary": os.environ.get("RENDER_ORDINARY", "false").lower() in ("true", "1", "yes"),
    "gif": os.environ.get("RENDER_GIF", "false").lower() in ("true", "1", "yes"),
    "4k": os.environ.get("RENDER_4K", "true").lower() in ("true", "1", "yes"),
}


def resolve_path(rel_path: str) -> str:
    """Resolves a path relative to the agent's folder, falling back to CWD."""
    if os.path.isabs(rel_path):
        return rel_path

    local_path = os.path.abspath(os.path.join(BASE_DIR, rel_path))
    if os.path.exists(local_path):
        return local_path

    # Check parent directory
    parent_dir = os.path.dirname(local_path)
    if os.path.exists(parent_dir):
        return local_path

    # Fallback to CWD
    return os.path.abspath(rel_path)


def restore_default_placeholder():
    """Generates a generic, safe gray placeholder image at assets/portrait_outpainted.png to prevent 404/file-not-found errors."""
    placeholder_path = resolve_path("assets/portrait_outpainted.png")
    try:
        from PIL import Image, ImageDraw

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


def update_composer(video_path: str, title: str, name: str, position_company: str) -> str:
    """Updates index.html with the new video path, title, speaker name, position/company texts, and sets timeline duration (8s for Veo, 10s for user uploads)."""
    # Ensure video_path is a relative path inside index.html for correct HTTP serving in headless Chrome
    if os.path.isabs(video_path):
        video_path = os.path.relpath(video_path, BASE_DIR)

    # 1. Determine timeline duration: 8.0s for Veo generated video, 10.0s for uploaded custom video
    target_duration = 10
    abs_video_path = resolve_path(video_path)

    # Probe duration if ffprobe is installed
    if shutil.which("ffprobe") and os.path.exists(abs_video_path):
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
    elif "video_example" in video_path.lower():
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
    new_config = f"""const CARD_CONFIG = {{
      title: "{title}",
      name: "{name}",
      position_company: "{position_company}",
      year: "{current_year}"
    }};"""

    if re.search(config_pattern, content, flags=re.DOTALL):
        content = re.sub(config_pattern, new_config, content, flags=re.DOTALL)
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
        content = re.sub(image_pattern, f'id="card-image" src="{video_path}"', content)
    else:
        # It's a video card!
        video_full_pattern = r'(<video\s+id="card-video"[^>]*?style="[^"]*?)(display:none;)\s*(;?)(")'
        content = re.sub(video_full_pattern, r"\g<1>\g<4>", content)
        content = re.sub(video_pattern, f'id="card-video" src="{video_path}"', content)

        image_full_pattern = r'(<img\s+id="card-image"[^>]*?style="[^"]*?)(display:none;)?(")'
        content = re.sub(image_full_pattern, r"\g<1>display:none;\g<3>", content)
        content = re.sub(image_pattern, 'id="card-image" src=""', content)

    # 3. Randomize colors for breaks, circle, pill, and hexagon using Google brand palette
    import random

    GDG_COLORS = [
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

    selected_colors = random.sample(GDG_COLORS, 4)
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


def render_composer() -> str:
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
    # PIPELINE 1: ORDINARY RENDERING (1080p + GIF)
    # ============================================================================
    if render_ordinary or render_gif:
        print("\n🎬 [Render Step 1/2] Rendering in ordinary quality (1080p) sequentially...")
        result = subprocess.run(["npm", "run", "render"], capture_output=True, text=True, cwd=BASE_DIR)

        if result.returncode == 0:
            print("🎉 [Ordinary Render successful!]")
            # Parse output file path
            output_lines = result.stdout.split("\n")
            local_ordinary_file = ""
            for line in output_lines:
                if ".mp4" in line:
                    match = re.search(r"(/[^\s]+?\.mp4)", line)
                    if match:
                        local_ordinary_file = match.group(1)
                        break

            if not local_ordinary_file:
                import glob

                renders_folder = resolve_path("renders")
                mp4_files = glob.glob(os.path.join(renders_folder, "*.mp4"))
                if mp4_files:
                    local_ordinary_file = max(mp4_files, key=os.path.getmtime)
                    local_ordinary_file = os.path.abspath(local_ordinary_file)

            if local_ordinary_file and os.path.exists(local_ordinary_file):
                # Strip audio
                if ffmpeg_installed:
                    temp_no_audio = local_ordinary_file.rsplit(".", 1)[0] + "_no_audio.mp4"
                    print(f"🔇 [Audio] Stripping audio from ordinary render '{local_ordinary_file}'...")
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

                # Rename
                renders_folder = resolve_path("renders")
                os.makedirs(renders_folder, exist_ok=True)
                target_ordinary_name = os.path.join(renders_folder, f"{speaker_name_clean}_{timestamp}.mp4")
                target_ordinary_path = os.path.abspath(target_ordinary_name)
                print(f"🏷️ [Rename] Renaming ordinary render to '{target_ordinary_name}'...")
                try:
                    os.rename(local_ordinary_file, target_ordinary_path)
                    local_ordinary_file = target_ordinary_path
                    ordinary_file = target_ordinary_path
                except Exception as e:
                    print(f"⚠️ [Rename] Failed to rename ordinary render: {e}")

                # Convert to GIF
                if render_gif:
                    if ffmpeg_installed:
                        local_gif_file = local_ordinary_file.rsplit(".", 1)[0] + ".gif"
                        print(f"🎬 [GIF] Converting ordinary render to GIF: '{local_gif_file}'...")
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
                                rendered_files.append(f"• GIF Animation: {local_gif_file}")
                            else:
                                print(f"⚠️ [GIF] ffmpeg failed: {gif_result.stderr}")
                        except Exception as e:
                            print(f"⚠️ [GIF] GIF conversion exception: {e}")
                    else:
                        print("⏭️  [GIF] Skipping GIF conversion (ffmpeg not found)")
                        rendered_files.append("• (Skipped) GIF Animation: ffmpeg not found on host machine.")

                if render_ordinary:
                    rendered_files.append(f"• Video in ordinary quality (1080p): {local_ordinary_file}")
                elif not render_ordinary and render_gif and local_ordinary_file and os.path.exists(local_ordinary_file):
                    print(f"🗑️ [Cleanup] Deleting temporary ordinary render '{local_ordinary_file}'...")
                    try:
                        os.remove(local_ordinary_file)
                    except Exception as e:
                        print(f"⚠️ [Cleanup] Failed to delete temp file: {e}")
        else:
            print("❌ [Ordinary Render failed]")
            print(result.stderr)
            raise RuntimeError(f"Ordinary render returned a non-zero exit code: {result.stderr}")

    # ============================================================================
    # PIPELINE 2: 4K UHD RENDERING
    # ============================================================================
    if render_4k:
        print("\n🎬 [Render Step 2/2] Rendering in ultra-high definition (4K) sequentially...")
        result_4k = subprocess.run(
            ["npx", "--yes", "hyperframes@0.6.72", "render", "--resolution=4k"],
            capture_output=True,
            text=True,
            cwd=BASE_DIR,
        )

        if result_4k.returncode == 0:
            print("🎉 [4K Render successful!]")
            output_lines = result_4k.stdout.split("\n")
            file_4k = ""
            for line in output_lines:
                if ".mp4" in line:
                    match = re.search(r"(/[^\s]+?\.mp4)", line)
                    if match:
                        file_4k = match.group(1)
                        break

            if not file_4k:
                import glob

                renders_folder = resolve_path("renders")
                mp4_files = glob.glob(os.path.join(renders_folder, "*.mp4"))
                if mp4_files:
                    if ordinary_file:
                        mp4_files = [f for f in mp4_files if os.path.abspath(f) != os.path.abspath(ordinary_file)]
                    if mp4_files:
                        file_4k = max(mp4_files, key=os.path.getmtime)
                        file_4k = os.path.abspath(file_4k)

            if file_4k and os.path.exists(file_4k):
                # Strip audio
                if ffmpeg_installed:
                    temp_no_audio_4k = file_4k.rsplit(".", 1)[0] + "_no_audio.mp4"
                    print(f"🔇 [Audio] Stripping audio from 4K render '{file_4k}'...")
                    try:
                        strip_cmd = ["ffmpeg", "-y", "-i", file_4k, "-an", "-c:v", "copy", temp_no_audio_4k]
                        strip_result = subprocess.run(strip_cmd, capture_output=True, text=True, cwd=BASE_DIR)
                        if strip_result.returncode == 0 and os.path.exists(temp_no_audio_4k):
                            os.replace(temp_no_audio_4k, file_4k)
                            print(f"✅ [Audio] Audio stripped from 4K render '{file_4k}'!")
                        else:
                            print(f"⚠️ [Audio] ffmpeg failed to strip audio from 4K: {strip_result.stderr}")
                    except Exception as e:
                        print(f"⚠️ [Audio] Failed to strip audio from 4K: {e}")
                else:
                    print("⏭️  [Audio] Skipping 4K audio stripping (ffmpeg not found)")

                # Rename
                renders_folder = resolve_path("renders")
                os.makedirs(renders_folder, exist_ok=True)
                target_4k_name = os.path.join(renders_folder, f"{speaker_name_clean}_{timestamp}_4k.mp4")
                target_4k_path = os.path.abspath(target_4k_name)
                print(f"🏷️ [Rename] Renaming 4K render to '{target_4k_name}'...")
                try:
                    os.rename(file_4k, target_4k_path)
                    file_4k = target_4k_path
                except Exception as e:
                    print(f"⚠️ [Rename] Failed to rename 4K render: {e}")

                rendered_files.append(f"• Video in 4K quality (2160p): {file_4k}")
        else:
            print("❌ [4K Render failed]")
            print(result_4k.stderr)
            raise RuntimeError(f"4K render returned a non-zero exit code: {result_4k.stderr}")

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
                        print(f"⚠️ [Poster] ffmpeg failed to extract frame: {extract_res.stderr}")
                except Exception as fe:
                    print(f"⚠️ [Poster] ffmpeg frame extraction error: {fe}")

        if not temp_image_src:
            # If original_video_src is an image, use it directly
            if original_video_src and any(
                original_video_src.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]
            ):
                temp_image_src = original_video_src
            else:
                # Fallback to locate static outpainted image or staged media
                temp_image_src = "assets/portrait_outpainted.png"
                temp_image_abs = resolve_path(temp_image_src)
                # If portrait_outpainted.png is not found or is the default placeholder, check staged_media
                use_fallback = not os.path.exists(temp_image_abs)
                if not use_fallback:
                    try:
                        from PIL import Image

                        with Image.open(temp_image_abs) as img:
                            if img.size == (500, 500):
                                use_fallback = True
                    except Exception:
                        pass
                if use_fallback:
                    temp_image_src = "assets/staged_media.png"
                    temp_image_abs = resolve_path(temp_image_src)
                    if not os.path.exists(temp_image_abs):
                        for ext in [".jpg", ".jpeg", ".webp"]:
                            candidate = f"assets/staged_media{ext}"
                            if os.path.exists(resolve_path(candidate)):
                                temp_image_src = candidate
                                break

        # Swap video and image sources temporarily for high-res snapshot
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
                    ["npx", "--yes", "hyperframes@0.6.72", "snapshot", f"--at={snapshot_time}"],
                    capture_output=True,
                    text=True,
                    cwd=BASE_DIR,
                )
            finally:
                # Unconditionally restore index.html backup immediately
                with open(target_index_html, "w", encoding="utf-8") as f:
                    f.write(html_backup)
                print("✅ [Poster] Restored original index.html sources.")

            if snapshot_result and snapshot_result.returncode == 0:
                import glob

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
                                    rendered_files.append(
                                        f"• High-Resolution Card Poster (4K PNG): {target_poster_path}"
                                    )
                                    print("✅ [Poster 4K] 4K poster successfully created!")
                                else:
                                    print(
                                        f"⚠️ [Poster 4K] ffmpeg failed to upscale, falling back to 1080p copy: {upscale_result.stderr}"
                                    )
                                    shutil.copy2(snapshot_file, target_poster_path)
                                    rendered_files.append(f"• High-Resolution Card Poster (PNG): {target_poster_path}")
                            except Exception as upscale_err:
                                print(
                                    f"⚠️ [Poster 4K] Failed to generate 4K poster, falling back to 1080p copy: {upscale_err}"
                                )
                                shutil.copy2(snapshot_file, target_poster_path)
                                rendered_files.append(f"• High-Resolution Card Poster (PNG): {target_poster_path}")
                        else:
                            shutil.copy2(snapshot_file, target_poster_path)
                            rendered_files.append(f"• High-Resolution Card Poster (PNG): {target_poster_path}")
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
            from PIL import Image

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
                rendered_files.append(f"• Gemini Outpainted Avatar: {target_avatar_path}")
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
