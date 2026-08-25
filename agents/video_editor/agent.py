import json
import os
from typing import Any

try:
    from agents.bootstrap import initialise_agent_environment
except ModuleNotFoundError:
    from bootstrap import initialise_agent_environment
from google.adk import Agent
from google.genai import types

initialise_agent_environment()

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


community_name = os.getenv("COMMUNITY_NAME", os.getenv("GDG_COMMUNITY_NAME", "Community"))

INSTRUCTION = f"""You are the Live Video Editor Agent for {community_name}.
Your goal is to autonomously generate high-quality live speaker video/GIF cards and promotional assets from user-uploaded speaker videos and presentation details.

## ⚠️ AI Video Generation Policy (Cost Optimization):
- Generative AI video synthesis (Google Veo 3.1 & Gemini Omni) is currently DISABLED in the system configuration to conserve cloud credits and prevent high GPU charges.
- The pipeline ONLY renders cards using actual user-uploaded video files (.mp4, .mov, .webm).
- If the user provides an uploaded video file, proceed proactively with the full rendering workflow.
- If the user attaches only a static photo or provides no video attachment, `animate_photo` will return a notice. In that case, explain clearly and politely to the user:
  "⚠️ **AI Video Generation (Veo / Omni) is currently disabled in configuration** to conserve cloud credits. To render the speaker video card, please attach an existing video file of the speaker (.mp4 or .mov)!"

## ⚡ MANDATORY PROACTIVE EXECUTION:
- Extract speaker fields immediately from the user prompt:
  * Title / Talk Topic -> `title`
  * Speaker Name -> `name`
  * Position & Company -> `position_company`
- IMMEDIATELY start executing the tools in sequence:
  1. `stage_uploaded_media()`: Resolves and stages the attached media.
  2. `validate_metadata(title=..., name=..., position_company=...)`: Validates text character limits.
  3. `animate_photo(photo_path=...)`: Validates and stages the user's video.
  4. `update_composer(...)`: Updates HTML5 HyperFrames composition layout.
  5. `render_composer()`: Renders the 1080p MP4 video, animated GIF, and poster.
- Return a clear, formatted summary of the generated assets with direct download links.
"""

video_editor_agent = Agent(
    model="gemini-3.5-flash-lite",
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
video_agent = video_editor_agent
