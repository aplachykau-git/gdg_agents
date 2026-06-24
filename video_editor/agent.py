import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.workflow import JoinNode, Workflow
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
# 📦 STRONGLY-TYPED WORKFLOW SCHEMAS
# ============================================================================


class VideoEditorInput(BaseModel):
    title: str = Field(description="The typewriter title of the speaker card (max 80 chars)")
    name: str = Field(description="The full name of the speaker (max 50 chars)")
    position_company: str = Field(description="The role and company of the speaker (max 80 chars)")
    photo_path: str = Field(default="", description="The local path to the media file if provided manually")


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
# ⚙️ WORKFLOW GRAPH NODES DEFINITIONS
# ============================================================================


async def stage_input(ctx: Context, node_input: VideoEditorInput) -> Event:
    """Stages the user uploaded media file from the session events or local path."""

    class MockToolContext:
        def __init__(self, session):
            self.session = session

    staged_path = await stage_uploaded_media(
        photo_path=node_input.photo_path, tool_context=MockToolContext(ctx.session)
    )
    return Event(
        output=staged_path,
        state={
            "title": node_input.title,
            "name": node_input.name,
            "position_company": node_input.position_company,
            "photo_path": staged_path,
        },
    )


def prepare_content_input(ctx: Context) -> ContentAgentInput:
    """Prepares the structured input for metadata validation."""
    return ContentAgentInput(
        title=ctx.state.get("title", ""),
        name=ctx.state.get("name", ""),
        position_company=ctx.state.get("position_company", ""),
    )


def validate_metadata_node(ctx: Context, node_input: ContentAgentInput) -> Event:
    """Validates the speaker text fields lengths."""
    validated_json = validate_metadata(
        title=node_input.title, name=node_input.name, position_company=node_input.position_company
    )
    return Event(output=validated_json, state={"validated_metadata": validated_json})


def prepare_media_input(ctx: Context) -> MediaAgentInput:
    """Prepares the structured input for media agent."""
    return MediaAgentInput(photo_path=ctx.state.get("photo_path", ""))


def process_media_result(node_input: Any) -> Event:
    """Extracts the resulting video path from the media agent output."""
    if not node_input:
        raise ValueError("Media agent returned empty content")

    # Extract text from node_input which can be types.Content, dict, or str
    if isinstance(node_input, str):
        text = node_input
    elif hasattr(node_input, "parts") and node_input.parts:
        text = node_input.parts[0].text or ""
    elif isinstance(node_input, dict) and "parts" in node_input:
        parts = node_input["parts"]
        if parts:
            first_part = parts[0]
            if isinstance(first_part, dict):
                text = first_part.get("text", "")
            else:
                text = getattr(first_part, "text", "")
        else:
            text = ""
    else:
        text = str(node_input)

    # Use a robust regex to find the file path ending with a standard media extension
    import re

    match = re.search(r"([a-zA-Z0-9_\-\.\/]+\.(?:mp4|mov|png|jpg|jpeg|webp))", text)
    if match:
        video_path = match.group(1)
    else:
        video_path = text.strip()

    return Event(output=video_path, state={"video_path": video_path})


def compile_and_render(ctx: Context, node_input: dict) -> Event:
    """Updates index.html with validated texts and renders ordinary, GIF, and 4K cards."""
    video_path = node_input.get("process_media_result", "")

    if video_path.startswith("Error:") or "error" in video_path.lower():
        raise ValueError(f"Media processing failed: {video_path}")

    title = ctx.state.get("title", "")
    name = ctx.state.get("name", "")
    position_company = ctx.state.get("position_company", "")

    # Update composer index.html
    update_res = update_composer(video_path=video_path, title=title, name=name, position_company=position_company)
    print(f"[Workflow] {update_res}")

    # Render composition
    render_res = render_composer()
    print(f"[Workflow] {render_res}")

    # Return the final message to display in UI
    ui_message = f"🎉 **Done! Speaker card has been successfully created.**\n\n{render_res}"
    content_event = types.Content(role="model", parts=[types.Part.from_text(text=ui_message)])
    return Event(output=render_res, content=content_event)


# ============================================================================
# 🤖 ORCHESTRATOR WORKFLOW GRAPH DEFINITION
# ============================================================================

join_node = JoinNode(name="join_validation_and_media")

root_workflow = Workflow(
    name="video_editor",
    description="Specialized workflow that coordinates speaker content and media processing, compiling premium Live Speaker Avatars.",
    input_schema=VideoEditorInput,
    edges=[
        ("START", stage_input),
        (stage_input, (prepare_content_input, prepare_media_input)),
        (prepare_content_input, validate_metadata_node),
        (prepare_media_input, media_agent),
        (media_agent, process_media_result),
        ((validate_metadata_node, process_media_result), join_node),
        (join_node, compile_and_render),
    ],
)


from typing import Any, AsyncGenerator

from google.adk.agents.invocation_context import InvocationContext


class WorkflowAgent(Agent):
    _workflow: Workflow

    def __init__(self, workflow: Workflow, description: str = ""):
        super().__init__(
            name=workflow.name,
            description=description or workflow.description,
            model="gemini-2.5-flash",
            instruction="This is a wrapped workflow agent.",
            input_schema=workflow.input_schema,
            output_schema=workflow.output_schema,
        )
        self._workflow = workflow
        self.mode = "single_turn"

    async def _run_impl(
        self,
        *,
        ctx: Context,
        node_input: Any,
    ) -> AsyncGenerator[Any, None]:
        async for event in self._workflow.run(ctx=ctx, node_input=node_input):
            yield event

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        adk_ctx = Context(ctx)
        node_input = None
        if ctx.user_content and ctx.user_content.parts:
            text = "".join(p.text for p in ctx.user_content.parts if p.text)
            if self.input_schema:
                try:
                    node_input = self.input_schema.model_validate_json(text)
                except Exception:
                    node_input = text
            else:
                node_input = text

        async for event in self._workflow.run(ctx=adk_ctx, node_input=node_input):
            yield event


root_agent = WorkflowAgent(root_workflow)
