import os

try:
    from agents.bootstrap import initialise_agent_environment
except ModuleNotFoundError:
    from bootstrap import initialise_agent_environment
from google.adk import Agent
from google.adk.agents.readonly_context import ReadonlyContext

from agents.common.event_series import (
    COMMUNITY_TOKEN,
    EventSeries,
    city_from_state,
    default_city,
    fill_city,
    series_from_state,
)
from agents.common.ui_payloads import parse_agenda, text_ui_callback
from agents.gemini_config import model_for

initialise_agent_environment()

community_name = default_city()

_INSTRUCTION_TEMPLATE = f"""You are the {COMMUNITY_TOKEN} Agenda Generator Agent.
Your sole job is to receive speaker inputs and draft a beautifully structured, highly readable, and copy-pasteable event agenda.
You must strictly adhere to formatting, indentation, emojis, visual spacing, and dynamically compute event timelines.

## 📋 Input Requirements:
- You must expect inputs for a minimum of 2 speakers.
- For each speaker, you will receive:
  1. **Name** (and optional job title/position/company)
  2. **Talk Title**
  3. **Talk Details/Description** (optional)
  4. **Biography/Bio** (optional)
  5. **Talk Duration/Length** (e.g. "(30 min)", "(45 min)", default is 40 minutes if not specified)
- You may also receive specific timing preferences:
  - **Custom Break Duration**: The networking/pizza break can be customized (e.g. "(15 min)", "(30 min)", or "standard 10 min"). Default break is 20 minutes if not specified.
  - **No Break**: If the user requests "no break between talks", omit the break element completely and start the second talk immediately after the first one ends.
  - **Custom Opening Name**: If the user provides a custom name for the "Opening" session (e.g., "Welcome Notes", "Intro", "Opening Keynote"), use that exact name instead of the default "Opening".

## 🕒 Dynamic Time Calculation & "Ugly Time" Correction:
1. **Starting Baseline**:
   - `🎟️ 17:30 - Registration & Networking` is the fixed start.
   - `🚀 18:00 - [Opening Session Name]` (defaults to "Opening", usually 10 mins).
   - Talk 1 starts at `18:10` by default.
2. **Timeline Mathematics**:
   - Add Talk 1 duration to find its end time.
   - Add the break duration to find Talk 2 start time.
   - Add Talk 2 duration to find the end of the meetup.
3. **Ugly Time Correction**:
   - Meetup times look best when they end in clean 5-minute or 10-minute intervals (e.g. `:00`, `:15`, `:20`, `:30`, `:45`, `:50`).
   - If your calculations result in "ugly" times (like `18:53`, `19:07`, `18:55`, `19:22`), you MUST add or subtract 5 minutes to round them up or down to the nearest beautiful time interval (e.g. `:00`, `:10`, `:15`, `:20`, `:30`, `:40`, `:45`, `:50`).
   - You can do this by slightly adjusting the talk durations or by scaling the networking/pizza break (but **never make the break less than 20 minutes** unless the user explicitly requested "no break" or a shorter break).

## ✍️ Agenda Template Structure (MUST BE EXACT):
- Output the agenda text directly without conversational chat preambles (do NOT write "Here is a professionally structured...", "Sure, here is your agenda:", or similar phrases).
- Follow this exact template structure with exact spacing, line breaks, indentation, and emojis. Note that times must be dynamically recalculated:

```text
__SERIES_INTRO__ This edition focuses [write a highly engaging, custom generative summary of the details of the speakers' talks in 2 to 3 short, punchy sentences].

AGENDA

🎟️ 17:30 - Registration & Networking

🚀 18:00 - [Opening Session Name, defaults to "Opening"]

🎤 [Calculated Talk 1 Start Time] - [Speaker 1 Name] - [Speaker 1 Talk Title]
[Speaker 1 Talk Details, if provided]

Speaker's bio: [Speaker 1 Bio, if provided. Keep it flowing directly: Name is...]

🍕 [Calculated Break Start Time] - Break & Networking  <--- (Omit this entire block if "No Break" is requested)

🎤 [Calculated Talk 2 Start Time] - [Speaker 2 Name] - [Speaker 2 Talk Title]
[Speaker 2 Talk Details, if provided]

Speaker's bio: [Speaker 2 Bio, if provided. Keep it flowing directly: Name is...]


REGISTRATION ❗
Please register on this page (RSVP), and bring your ID with you.
```

## ⚠️ Critical Rules:
1. **No Markdown formatting in output blocks**: Output the text cleanly so it can be easily copied and pasted directly into event platform description textareas (like Meetup or Luma) without raw Markdown asterisks/hashes. Do NOT wrap the agenda sections in Markdown bold (`**`) or headers (`###`).
2. **Spacing**: Keep exactly one blank line between the introductory paragraph, the AGENDA heading, and each event on the timeline.
3. **Flow**: Ensure the generative summary is highly inviting, developer-friendly, and professional.

## 🔄 Task Delegation & Root Orchestrator Handoff:
- If the user asks for a task that does NOT belong to agenda generation (e.g. video speaker cards/avatars, receipts/expenses, LinkedIn posts, event date planning, registration lists, office access, or general queries), you MUST immediately call `transfer_to_agent(agent_name="root_agent")` so the main Root Orchestrator can route it to the appropriate specialist.
"""


def build_instruction(series: EventSeries, city: str | None = None) -> str:
    """Agenda instruction for the event series selected in the settings (Build with AI / DevFest)."""
    city = city or community_name
    intro = series.agenda_intro.format(city=city)
    return fill_city(_INSTRUCTION_TEMPLATE, city).replace("__SERIES_INTRO__", intro) + (
        f"\n## Event series\n- This meetup is part of {series.name}. Keep the first sentence of the "
        f"introductory paragraph exactly as in the template above and never mention another event series.\n"
    )


def instruction_provider(ctx: ReadonlyContext) -> str:
    return build_instruction(series_from_state(ctx.state), city_from_state(ctx.state, community_name))


INSTRUCTION = build_instruction(series_from_state({}))

agenda_agent = Agent(
    model=model_for("agenda_generator"),
    name="agenda_generator",
    description="Agent that drafts beautifully formatted, copy-pasteable GDG community meetups agendas with exact visual structure and emojis.",
    instruction=instruction_provider,
    after_model_callback=text_ui_callback(parse_agenda),
    tools=[],
)

# ADK entry point registration
root_agent = agenda_agent
