import json
import os
from typing import Any

from dotenv import load_dotenv
from google.adk import Agent
from google.genai import types

load_dotenv(override=True)

# BASE_DIR represents the absolute path of this agent's folder, ensuring self-contained integrations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Import tools from submodule
from .tools.composer_tools import render_composer, update_composer
from .tools.media_tools import animate_photo, stage_uploaded_media, verify_portrait_photo

# ============================================================================
# 🔒 SAFETY & MODERATION CONFIGURATIONS
# ============================================================================

safety_text_config = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    ),
]

# ============================================================================
# 🛠️ CONTENT VALIDATION TOOL
# ============================================================================


def validate_metadata(title: str, name: str, position_company: str) -> str:
    """Validates speaker card metadata character length rules.

    Args:
        title: Title of the speaker card (max 80 chars).
        name: Name of the speaker (max 50 chars).
        position_company: Role and company of the speaker (max 80 chars).

    Returns:
        JSON string representing the successfully validated metadata, or Error message.
    """
    print("📝 [Content Validation] Validating speaker texts...")
    print(f'   ├─ Title: "{title}" (len: {len(title)})')
    print(f'   ├─ Name: "{name}" (len: {len(name)})')
    print(f'   └─ Position & Company: "{position_company}" (len: {len(position_company)})')

    MAX_TITLE_LEN = 80
    MAX_NAME_LEN = 50
    MAX_POSITION_COMPANY_LEN = 80

    validation_errors = []
    if len(title) > MAX_TITLE_LEN:
        validation_errors.append(
            f'Title length ({len(title)} chars) exceeds limit of {MAX_TITLE_LEN} chars. Text: "{title}"'
        )
    if len(name) > MAX_NAME_LEN:
        validation_errors.append(
            f'Speaker Name length ({len(name)} chars) exceeds limit of {MAX_NAME_LEN} chars. Text: "{name}"'
        )
    if len(position_company) > MAX_POSITION_COMPANY_LEN:
        validation_errors.append(
            f'Position & Company length ({len(position_company)} chars) exceeds limit of {MAX_POSITION_COMPANY_LEN} chars. Text: "{position_company}"'
        )

    if validation_errors:
        error_msg = "Error: Text field character limits exceeded!\n" + "\n".join(validation_errors)
        print(f"❌ [Validation Error] {error_msg}")
        return error_msg

    result = {"title": title.strip(), "name": name.strip(), "position_company": position_company.strip()}
    print("✅ [Content Validation] Validation passed!")
    return json.dumps(result)


# ============================================================================
# 🤖 LIVE VIDEO EDITOR AGENT
# ============================================================================

INSTRUCTION = """You are the Live Video Editor Agent for GDG Krakow.
Your goal is to autonomously generate high-quality live speaker video/GIF cards and promotional avatars from speaker portrait photos/videos and presentation details.

## ⚡ MANDATORY PROACTIVE EXECUTION:
- NEVER ask conversational questions if the user has provided speaker details (such as title, name, company, bio) or media in the conversation!
- Extract the fields immediately from the user prompt:
  * Title / Talk Topic -> `title`
  * Speaker Name -> `name`
  * Position & Company -> `position_company`
- IMMEDIATELY start executing the tools in sequence. Do NOT ask for confirmation or re-ask for details.

## 🎬 Step-by-Step Execution Workflow:

1. **Stage Media**:
   - Always call `stage_uploaded_media()` first to resolve and stage the user's attached photo/video in the workspace. It returns the staged path (e.g. `assets/staged_media.mp4` or `assets/staged_media.jpg`).

2. **Validate Speaker Details**:
   - Call `validate_metadata(title=..., name=..., position_company=...)` with the extracted details to ensure texts fit character limits (Title <= 80, Name <= 50, Position/Company <= 80).
   - If validation returns an error, notify the user with the exact limits.

3. **Verify & Animate**:
   - If the staged asset is an image/photo, call `verify_portrait_photo(photo_path=...)` with the staged path, then call `animate_photo(photo_path=..., creative_prompt=...)`.
   - If the staged asset is already a video (e.g. `assets/staged_media.mp4`), skip `verify_portrait_photo` and call `animate_photo(photo_path=...)`.
   - Note the returned `video_path` from `animate_photo`.

4. **Update HTML5 Composer & Render**:
   - Call `update_composer(video_path=..., title=..., name=..., position_company=...)` with the video path and speaker details.
   - Call `render_composer()` to compile the video cards (MP4 video, animated GIF, and 4K preview).

5. **Final Output**:
   - Return a clear, formatted summary of the generated assets, paths, and status to the user.
"""

video_editor_agent = Agent(
    model="gemini-2.5-flash",
    name="video_editor",
    description="Live Video Editor agent that validates speaker metadata, verifies portrait face, outpaints/animates background video with Veo, updates HTML5 canvas composer, and renders final video/GIF speaker cards.",
    instruction=INSTRUCTION,
    tools=[
        stage_uploaded_media,
        validate_metadata,
        verify_portrait_photo,
        animate_photo,
        update_composer,
        render_composer,
    ],
    generate_content_config=types.GenerateContentConfig(safety_settings=safety_text_config),
)

# ADK entry point registration
root_agent = video_editor_agent
