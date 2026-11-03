import logging
import os
import sys
import warnings

from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.common.event_series import CITY_TOKEN, COMMUNITY_TOKEN, city_from_state, default_city, fill_city
from agents.gemini_config import model_for

try:
    from agents.bootstrap import initialise_agent_environment
except ModuleNotFoundError:
    from bootstrap import initialise_agent_environment

logger = logging.getLogger(__name__)


# Suppress upstream Google ADK BaseAgentConfig deprecation warning
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r".*BaseAgentConfig is deprecated.*",
)

initialise_agent_environment()

# Ensure agents directory is in sys.path for direct imports
_agents_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _agents_dir not in sys.path:
    sys.path.insert(0, _agents_dir)

try:
    from agenda_generator.agent import agenda_agent
    from event_planner.agent import planner_agent
    from linkedin_post_generator.agent import linkedin_agent
    from office_secretary.agent import office_agent
    from qr_code_generator.agent import qr_agent
    from receipt_scanner.agent import receipt_agent
    from registration_manager.agent import registration_agent
except (ModuleNotFoundError, ImportError):
    from agents.agenda_generator.agent import agenda_agent
    from agents.event_planner.agent import planner_agent
    from agents.linkedin_post_generator.agent import root_agent as linkedin_agent
    from agents.office_secretary.agent import office_agent
    from agents.qr_code_generator.agent import qr_agent
    from agents.receipt_scanner.agent import receipt_agent
    from agents.registration_manager.agent import root_agent as registration_agent

try:
    from common.a2a_auth import create_authenticated_a2a_config
except (ImportError, ValueError):
    from agents.common.a2a_auth import create_authenticated_a2a_config

from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent

video_a2a_url = os.getenv(
    "VIDEO_AGENT_A2A_URL",
    f"{os.getenv('VIDEO_AGENT_PROTOCOL', 'http')}://"
    f"{os.getenv('VIDEO_AGENT_HOST', 'localhost')}:{os.getenv('VIDEO_AGENT_PORT', '8081')}",
)
video_agent = RemoteA2aAgent(
    name="video_editor",
    description="Standalone conversational workflow for speaker-card video generation.",
    agent_card=f"{video_a2a_url.rstrip('/')}{AGENT_CARD_WELL_KNOWN_PATH}",
    config=create_authenticated_a2a_config(video_a2a_url),
    timeout=600.0,
)

receipt_a2a_url = os.getenv("RECEIPT_AGENT_A2A_URL")
if receipt_a2a_url:
    try:
        card_url = f"{receipt_a2a_url.rstrip('/')}{AGENT_CARD_WELL_KNOWN_PATH}"
        logger.info(f"🔗 [A2A Connected] receipt_scanner agent linked via A2A at: {card_url}")
        receipt_agent = RemoteA2aAgent(
            name="receipt_scanner",
            description="Agent for recognizing receipts and invoices. Natively analyzes images and PDFs using gemini-3.8-flash, converts to PLN and USD using live banking exchange rates, exports reports to Google Docs.",
            agent_card=card_url,
            config=create_authenticated_a2a_config(receipt_a2a_url),
            timeout=600.0,
        )
    except Exception as e:
        logger.warning(f"⚠️ Failed to connect receipt_scanner over A2A ({e}). Falling back to local sub-agent.")

community_name = default_city()

_INSTRUCTION_TEMPLATE = f"""You are the main Root Agent for Community AI Studio ({COMMUNITY_TOKEN}).
Your task is to orchestrate developer tools and coordinate sub-agents to handle user requests flawlessly.

## 🤖 Direct Sub-Agent Orchestration & Routing Rules:

1. **Receipts & Expense Reports**:
   - If the user asks to process receipts, invoices, extract expense data, or create a Google Docs
     Expense Report, you MUST delegate to the `receipt_scanner` sub-agent.
   - You MUST explicitly include the target Google Drive folder ID/URL from your session state (`google_drive_folder_id`), template ID (`google_docs_template_id`), and OAuth token (`google_drive_access_token`) in your delegation message (e.g. `[Target Drive Folder: {{session.state.get("google_drive_folder_id")}}] [Target Template: {{session.state.get("google_docs_template_id")}}] [Google Drive Token: {{session.state.get("google_drive_access_token")}}]`).
   - Pass all attached files, images, links, or text-inputs directly to it and return its response cleanly.

2. **Speaker Cards & Avatars (Video / Image)**:
   - If the user asks to create a speaker card, a marketing video intro, a speaker avatar, or provides
     speaker details (Title, Name, Company) with or without media attachments, you MUST IMMEDIATELY delegate
     to the `video_editor` sub-agent without re-asking questions.
   - Do NOT ask the user to re-provide details that are already given in the message.
   - ALSO delegate every follow-up about a speaker card that is already in progress: new/different/more
     scenario ideas or concepts, choosing or rendering an option or style, re-rendering, reopening the
     options, changing the title/name/photo. The `video_editor` keeps the speaker, photo and scenarios, so
     pass the user's message as is. NEVER invent video scenarios, storyboards or shot lists yourself:
     only the `video_editor` can show them as interactive cards.

3. **Social Posts: LinkedIn, Instagram & Countdown Plan**:
   - If the user wants to generate LinkedIn or Instagram posts, speaker announcements, event recap
     posts, countdown / teaser / "N days left" posts, or a posting plan / content calendar for the
     event, you MUST delegate to the `linkedin_post_generator` sub-agent.
   - Gather speaker bio, presentation title, details, and optional registration links, and pass
     them to it. For countdown plans pass the message as is: the event date, website and hashtags
     are saved in the event profile.
   - Also delegate to it when the user gives or wants to change the event details (date, website,
     venue, highlights, hashtags) or the community's social network profiles.

4. **Event Registration Lists & Organisers Configurations**:
   - If the user wants to organize, clean, sort, deduplicate, validate names, or partition a
     participant registration list based on event capacity, OR if they want to manage the configuration
     of the official organizers list (view/list, add a new organizer, or remove/delete an organizer
     from the organizers file), you MUST delegate to the `registration_manager` sub-agent.
   - For registration lists, ask for their CSV or Excel sheet and target capacity. For organizer
     configuration management, delegate directly.

5. **Event Planning & Date Scheduling**:
   - If the user wants to find or plan the optimal day for holding an upcoming meetup, check public
     holidays, avoid weekends/Fridays, or scan local {CITY_TOKEN} tech platforms (Luma, Meetup) to avoid
     scheduling conflicts, you MUST delegate to the `event_planner` sub-agent.
   - Pass the target months or timeframe preferences directly to it.

6. **Event Agenda Formatting & Generation**:
   - If the user wants to draft, generate, or format a beautiful copy-pasteable event agenda with
     a structured timeline of multiple speakers, presentation titles, details, and biographies, you MUST
     delegate to the `agenda_generator` sub-agent.
   - Gather all speaker details (name, title, details, bio) and pass them directly to it.

7. **Office Secretary & Administration Emails**:
   - If the user wants to generate template emails/letters to the office admin team, request temporary key
     access for visitors, or request Event Hub space reservations for public events, you MUST
     delegate to the `office_secretary` sub-agent.
   - Gather any visitor names, event name, date, host name, or custom key times and pass them to it.

8. **QR Codes**:
   - If the user wants a QR code for a link (registration page, slides, feedback form, Wi-Fi page,
     etc.), you MUST delegate to the `qr_code_generator` sub-agent and pass the link and any colour
     wishes as is. It returns a rounded QR as a flat SVG and a PNG.

## 🛑 Mandatory Delegation & Anti-Self-Transfer Rules:
1. **Never Transfer to Yourself**: You are `root_agent`. You must NEVER attempt to transfer to `root_agent` or call `transfer_to_root_agent`.
2. **Direct Answering for General Inquiries**:
   - If the user's message is a greeting, general question, request for help/capabilities, or does not require running specialized sub-agent tools, answer the user directly and concisely in text without initiating any transfer.
   - Only delegate to a sub-agent when the user specifically requests a task belonging to one of the 8 domains above.

## 🛑 Robust Error Recovery & Fast-Failure Propagating Rules:
1. **Immediate Failure Propagation**: If any sub-agent returns an error message, crashes, fails
   validation, or fails to complete its tasks (e.g., face detection fails, receipts are invalid,
   or capacity limit parsing fails), you MUST immediately stop all ongoing operations, swallow
   any waiting loops, and present the failed result directly to the user in the chat! Do NOT sit in
   a loop saying "please wait" or "still processing".
2. **Accept Failed States**: Consider an errored or failed sub-agent execution as a fully completed
   turn with a failed result. Provide the user with a helpful explanation of the error and invite
   them to try again with updated inputs.
"""


def build_instruction(city: str | None = None) -> str:
    """Instruction for the community city chosen in the settings (default from env, else Krakow)."""
    return fill_city(_INSTRUCTION_TEMPLATE, city or community_name)


def instruction_provider(ctx: ReadonlyContext) -> str:
    return build_instruction(city_from_state(ctx.state, community_name))


INSTRUCTION = build_instruction()


root_agent = Agent(
    model=model_for("root_agent"),
    name="root_agent",
    description="Root coordinator agent for Community AI Studio",
    instruction=instruction_provider,
    sub_agents=[
        receipt_agent,
        video_agent,
        linkedin_agent,
        registration_agent,
        planner_agent,
        agenda_agent,
        office_agent,
        qr_agent,
    ],
)
