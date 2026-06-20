import json
import os
import sys

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.tools.agent_tool import AgentTool
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv(override=True)

# BASE_DIR represents the absolute path of this agent's folder, ensuring self-contained integrations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Use relative imports for submodules within the package
from .tools.composer_tools import render_composer, update_composer
from .tools.media_tools import animate_photo, stage_uploaded_media, verify_portrait_photo

# ============================================================================
# 🔒 SAFETY & MODERATION CONFIGURATIONS
# ============================================================================

safety_text_config = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,  # Strict blocking
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
        JSON string representing the successfully validated metadata.
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
        error_msg = "Text field character limits exceeded!\n" + "\n".join(validation_errors)
        print(f"❌ [Validation Error] {error_msg}")
        raise ValueError(error_msg)

    result = {"title": title.strip(), "name": name.strip(), "position_company": position_company.strip()}
    print("✅ [Content Validation] Validation passed!")
    return json.dumps(result)


# ============================================================================
# 📦 STRONGLY-TYPED SUB-AGENT SCHEMAS
# ============================================================================


class ContentAgentInput(BaseModel):
    title: str = Field(description="The typewriter title of the speaker card (max 80 chars)")
    name: str = Field(description="The full name of the speaker (max 50 chars)")
    position_company: str = Field(description="The role and company of the speaker (max 80 chars)")


class MediaAgentInput(BaseModel):
    photo_path: str = Field(
        description="The local staged media path returned by stage_uploaded_media (e.g. assets/staged_media.png)"
    )


# ============================================================================
# 🤖 SUB-AGENTS DEFINITIONS
# ============================================================================

# content_agent accepts texts, validates length, checks safety, and generates speaker JSON config
content_agent = Agent(
    name="content_agent",
    description="Validates metadata fields (title, name, position_company), checks safety, and generates a formatted JSON configuration.",
    model="gemini-2.5-flash",
    input_schema=ContentAgentInput,
    instruction=(
        "You are the Speaker Card Content Editor sub-agent.\n"
        "Your task is to take the speaker's metadata (Title, Speaker Name, Position & Company) "
        "provided in your input schema, and perform validation using the `validate_metadata` tool.\n"
        "If the metadata is valid, output the final verified JSON string and hand control back "
        "to the orchestrator.\n"
        "If there are any validation errors or safety issues, report them clearly so the execution "
        "can be corrected."
    ),
    tools=[validate_metadata],
    generate_content_config=types.GenerateContentConfig(safety_settings=safety_text_config),
)

# media_agent processes media files, validates human faces, runs outpainting, and generates videos
media_agent = Agent(
    name="media_agent",
    description="Processes portrait images, outpaints, performs face detection verification, and generates background video via Google Veo.",
    model="gemini-2.5-flash",
    input_schema=MediaAgentInput,
    instruction=(
        "You are the Speaker Card Media Engineer sub-agent.\n"
        "Your job is to prepare the final background video asset for the card:\n"
        "1. Check the `photo_path` from your input schema.\n"
        "2. If it is a video file (ends with .mp4, .mov, etc.), call `animate_photo` with that path "
        "and a dummy creative prompt. It will directly return the video path.\n"
        "3. If it is a portrait photo:\n"
        "   - You MUST first run portrait face detection by calling the `verify_portrait_photo` "
        "tool on the photo_path. If face verification fails or raises an error, immediately halt "
        "and return a clear error message (starting strictly with 'Error: No recognizable human face "
        "was detected in the photo').\n"
        "   - If face verification succeeds, write a detailed cinematic prompt and call `animate_photo` "
        "with the photo path and your prompt to generate the video. (The `animate_photo` tool will "
        "automatically handle whether to animate via Veo or outpaint as a static image based on "
        "environment configuration).\n"
        "   - If you notice that Veo animation is disabled in the config (e.g. static fallback path "
        "returned), kindly notify the user that the card will be rendered with their static "
        "outpainted portrait.\n"
        "4. Return the path of the final background video/image (or the 'Error:' message) "
        "back to the main agent."
    ),
    tools=[verify_portrait_photo, animate_photo],
    generate_content_config=types.GenerateContentConfig(safety_settings=safety_text_config),
)

# ============================================================================
# 🤖 WRAP SUB-AGENTS AS STRONGLY-TYPED ADK TOOLS
# ============================================================================

content_agent_tool = AgentTool(content_agent)
media_agent_tool = AgentTool(media_agent)

# ============================================================================
# 🤖 ORCHESTRATOR ROOT AGENT DEFINITION
# ============================================================================

# root_agent coordinates sub-agents and final rendering compiler
root_agent = Agent(
    name="video_editor",
    description="Specialized sub-agent that coordinates speaker content and media processing, compiling premium Live Speaker Avatars.",
    model="gemini-2.5-flash",
    instruction=(
        "You are the Live Speaker Avatars Video Editor Agent (Google ADK 2.0).\n"
        "Your workflow to create a premium Live Speaker Avatars card is:\n"
        "1. Ask the user to upload/provide their custom portrait photo or a custom background "
        "video file, and supply the texts: Title, Speaker Name, and Position & Company.\n"
        "   CRITICAL: Do NOT start validation or invoke any tools unless a custom portrait photo or "
        "custom background video file has been explicitly provided/uploaded by the user. There is "
        "NO default fallback.\n"
        "   CRITICAL: Inform the user about character length limits:\n"
        "     - Title: max 80 characters\n"
        "     - Speaker Name: max 50 characters\n"
        "     - Position & Company: max 80 characters\n"
        "     Warn them that exceeding these limits will fail validation and block rendering.\n"
        "2. Once the user uploads the media, you MUST first run the `stage_uploaded_media` tool to "
        "save their active upload to a deterministic local path. If the user uploaded the media directly "
        "in the chat, invoke `stage_uploaded_media` with an empty string as `photo_path`.\n"
        "3. Once staged, you MUST invoke both sub-agent tools in parallel in a single turn:\n"
        "   - Call `content_agent` with parameters (title, name, position_company) to validate the "
        "metadata text and format the JSON.\n"
        "   - Call `media_agent` with parameter (photo_path) passing the staged path returned by "
        "`stage_uploaded_media` to perform face verification and generate the background video.\n"
        "4. In the next turn, once you receive the results from both sub-agents (validated JSON and "
        "video path):\n"
        "   - CRITICAL: Before calling `update_composer` or `render_composer`, you MUST check the result "
        "returned by `media_agent`. If the returned path starts with 'Error:', describes a face "
        "verification failure, or is otherwise invalid as a file path, you MUST immediately halt, "
        "skip `update_composer` and `render_composer` entirely, and report the specific failure message "
        "clearly to the user, explaining that the card generation has failed.\n"
        "   - If the path is valid, immediately call `update_composer` with the video path, title, "
        "name, and position_company to update the index.html.\n"
        "   - Immediately call `render_composer` to sequentially render ordinary, GIF, and 4K media "
        "cards.\n"
        "   CRITICAL: You MUST execute `update_composer` and `render_composer` in the same turn right "
        "after receiving the sub-agents' responses! Do NOT wait or ask the user for permission.\n"
        "5. Share a friendly confirmation with the user outlining the rendered assets.\n"
        "CRITICAL ERROR RECOVERY RULE:\n"
        "If any sub-agent tool, staging tool, validation, or rendering step fails or raises a "
        "ValueError/exception (e.g. invalid photo, face validation failed, or character limit exceeded), "
        "you MUST immediately report the failure message clearly to the user in the chat, explain what "
        "went wrong, and explicitly tell them that they can start a completely fresh attempt by uploading "
        "a new photo/video and providing new texts.\n"
        "Do NOT tell the user that you are 'still processing' or 'waiting' for sub-agents if a tool has "
        "already errored. Once a tool fails, consider the previous execution cycle fully terminated, "
        "and allow a new execution to begin."
    ),
    sub_agents=[content_agent, media_agent],
    tools=[stage_uploaded_media, content_agent_tool, media_agent_tool, update_composer, render_composer],
)
