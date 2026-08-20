from dotenv import load_dotenv

load_dotenv(override=True)

import os

from google.adk import Agent

try:
    from agenda_generator.agent import agenda_agent
    from event_planner.agent import planner_agent
    from linkedin_post_generator.agent import root_agent as linkedin_agent
    from office_secretary.agent import office_agent
    from receipt_scanner.agent import receipt_agent
    from registration_manager.agent import root_agent as registration_agent
    from video_editor.agent import root_agent as video_agent
except ModuleNotFoundError:
    from agents.agenda_generator.agent import agenda_agent
    from agents.event_planner.agent import planner_agent
    from agents.linkedin_post_generator.agent import root_agent as linkedin_agent
    from agents.office_secretary.agent import office_agent
    from agents.receipt_scanner.agent import receipt_agent
    from agents.registration_manager.agent import root_agent as registration_agent
    from agents.video_editor.agent import root_agent as video_agent

# Support A2A (Agent-to-Agent) remote connections if URLs are configured
video_a2a_url = os.getenv("VIDEO_AGENT_A2A_URL")
if video_a2a_url:
    try:
        from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent
        card_url = f"{video_a2a_url.rstrip('/')}{AGENT_CARD_WELL_KNOWN_PATH}"
        print(f"🔗 [A2A Connected] video_editor agent linked via A2A at: {card_url}")
        video_agent = RemoteA2aAgent(
            name="video_editor",
            description="Live Video Editor agent that validates speaker metadata, verifies portrait face, outpaints/animates background video with Veo, updates HTML5 canvas composer, and renders final video/GIF speaker cards.",
            agent_card=card_url,
        )
    except Exception as e:
        print(f"⚠️ Failed to connect video_editor over A2A ({e}). Falling back to local sub-agent.")

receipt_a2a_url = os.getenv("RECEIPT_AGENT_A2A_URL")
if receipt_a2a_url:
    try:
        from google.adk.agents.remote_a2a_agent import AGENT_CARD_WELL_KNOWN_PATH, RemoteA2aAgent
        card_url = f"{receipt_a2a_url.rstrip('/')}{AGENT_CARD_WELL_KNOWN_PATH}"
        print(f"🔗 [A2A Connected] receipt_scanner agent linked via A2A at: {card_url}")
        receipt_agent = RemoteA2aAgent(
            name="receipt_scanner",
            description="Agent for recognizing receipts and invoices. Natively analyzes images and PDFs using gemini-2.5-pro, converts to PLN and USD using the Pekao rate, exports reports to Google Docs.",
            agent_card=card_url,
        )
    except Exception as e:
        print(f"⚠️ Failed to connect receipt_scanner over A2A ({e}). Falling back to local sub-agent.")

community_name = os.getenv("GDG_COMMUNITY_NAME", "Krakow")

INSTRUCTION = f"""You are the main Root Agent for GDG {community_name}.
Your task is to orchestrate developer tools and coordinate sub-agents to handle user requests flawlessly.

## 🤖 Direct Sub-Agent Orchestration & Routing Rules:

1. **Receipts & Expense Reports**:
   - If the user asks to process receipts, invoices, extract expense data, or create a Google Docs
     Expense Report, you MUST delegate to the `receipt_scanner` sub-agent.
   - Pass any files, links, or text-inputs directly to it and return its response cleanly.

2. **Speaker Cards & Avatars (Video / Image)**:
   - If the user asks to create a speaker card, a marketing video intro, a speaker avatar, or provides
     speaker details (Title, Name, Company) with or without media attachments, you MUST IMMEDIATELY delegate
     to the `video_editor` sub-agent without re-asking questions.
   - Do NOT ask the user to re-provide details that are already given in the message.

3. **LinkedIn Announcement & Recap Posts**:
   - If the user wants to generate LinkedIn promotional posts, speaker announcements, or event recap
     posts, you MUST delegate to the `linkedin_post_generator` sub-agent.
   - Gather speaker bio, presentation title, details, and optional registration links, and pass
     them to it.

4. **Event Registration Lists & Organisers Configurations**:
   - If the user wants to organize, clean, sort, deduplicate, validate names, or partition a
     participant registration list based on event capacity, OR if they want to manage the configuration
     of the official organizers list (view/list, add a new organizer, or remove/delete an organizer
     from the organizers file), you MUST delegate to the `registration_manager` sub-agent.
   - For registration lists, ask for their CSV or Excel sheet and target capacity. For organizer
     configuration management, delegate directly.

5. **Event Planning & Date Scheduling**:
   - If the user wants to find or plan the optimal day for holding an upcoming meetup, check public
     holidays, avoid weekends/Fridays, or scan local {community_name} tech platforms (Luma, Meetup) to avoid
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

## 🛑 Mandatory Delegation & Anti-Self-Transfer Rules:
1. **Never Transfer to Yourself**: You are `root_agent`. You must NEVER attempt to transfer to `root_agent` or call `transfer_to_root_agent`.
2. **Direct Answering for General Inquiries**:
   - If the user's message is a greeting, general question, request for help/capabilities, or does not require running specialized sub-agent tools, answer the user directly and concisely in text without initiating any transfer.
   - Only delegate to a sub-agent when the user specifically requests a task belonging to one of the 7 domains above.

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

root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="Root coordinator agent of GDG {community_name}",
    instruction=INSTRUCTION,
    sub_agents=[
        receipt_agent,
        video_agent,
        linkedin_agent,
        registration_agent,
        planner_agent,
        agenda_agent,
        office_agent,
    ],
)
