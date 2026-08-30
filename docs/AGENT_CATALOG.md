# Agent Catalog

## Architecture Overview

The system follows a hub-and-spoke model. The **Root Orchestrator** receives all user requests, parses intent, and delegates to one of seven specialized agents. Five agents run in-process (local sub-agents); two run as isolated private Cloud Run microservices connected over OIDC-authenticated A2A.

```
Root Orchestrator
├── [local]  LinkedIn Post Generator
├── [local]  Registration Manager
├── [local]  Event Planner
├── [local]  Agenda Generator
├── [local]  Office Secretary
├── [A2A]    Video Editor          (port 8081 / Cloud Run private)
└── [A2A]    Receipt Scanner       (port 8082 / Cloud Run private)
```

---

## root_agent — Root Orchestrator

| | |
|:---|:---|
| **Model** | `gemini-3.5-flash-lite` |
| **Type** | Local, in-process |
| **Entry point** | `agents/root_agent/agent.py` |

**Responsibilities:** Intent parsing, routing, error propagation. Maintains session state (`google_drive_folder_id`, `google_docs_template_id`) and injects it into sub-agent delegation messages. Configured with all seven sub-agents as children.

**Routing domains:**

| Trigger | Delegates to |
|:---|:---|
| Receipts, invoices, expense reports | `receipt_scanner` |
| Speaker cards, marketing video intros | `video_editor` |
| LinkedIn posts, event recap copy | `linkedin_post_generator` |
| Registration lists, organiser config | `registration_manager` |
| Event date scheduling, meetup conflicts | `event_planner` |
| Agenda drafting and formatting | `agenda_generator` |
| Office key access, Event Hub reservation emails | `office_secretary` |

**Error handling:** Immediately surfaces sub-agent failures to the user without retrying or waiting. Treats an errored sub-agent turn as a completed failed turn.

---

## linkedin_post_generator — LinkedIn Post Generator

| | |
|:---|:---|
| **Model** | `gemini-3.5-flash-lite` (temperature 1.0) |
| **Type** | Local, in-process |
| **Entry point** | `agents/linkedin_post_generator/agent.py` |
| **Tools** | None (pure generation) |

**Responsibilities:** Generates exactly 3 style-variant LinkedIn announcement posts or event recap summaries from speaker bio, talk title, and talk description.

**Key constraints:**
- Requires speaker name, position, company, bio, talk title, and talk description before generating
- Never quotes the full talk title verbatim in post body (speaker card renders it visually)
- Enforces strict anti-hallucination: talk content derived only from description, bio content only from bio
- Mandatory `#GDG{COMMUNITY_NAME}` hashtag in every variant; 3–4 hashtags total
- Each variant: exactly 2–3 prose paragraphs, one CTA, one approved emoji

**Output:** 3 Markdown-formatted post variants with headers `### Variant N: Style Name`.

**Evals:** Two-tier suite — deterministic contract checks + LLM-as-Judge semantic scoring. See `docs/linkedin_post_generator_evals.md`.

---

## registration_manager — Registration Manager

| | |
|:---|:---|
| **Model** | `gemini-3.5-flash-lite` |
| **Type** | Local, in-process |
| **Entry point** | `agents/registration_manager/agent.py` |
| **Tools** | `process_registrations`, `stage_uploaded_registration`, `stage_manual_text_registrations`, `get_organisers_list`, `add_organiser`, `remove_organiser` |

**Responsibilities:** Cleans, deduplicates, and partitions event registration lists (CSV/Excel) into confirmed and waitlisted groups. Manages the persistent organisers list file.

**Key capabilities:**
- Name normalization: filters initials, symbols, test entries
- Deduplication by earliest timestamp
- Latin/Cyrillic/other script separation with per-group alphabetical sort
- Fuzzy phonetic matching of organiser names (dynamic, never hardcoded)
- Manual override list to force-confirm specific attendees (VIPs, organizers)
- Organiser CRUD: view, add, remove from `configs/organisers.txt`

**Privacy:** Never prints individual attendee names in chat. Outputs only summary statistics; DOCX download and copy buttons are rendered by the UI from tool payload.

---

## event_planner — Event Planner

| | |
|:---|:---|
| **Model** | `gemini-3.5-flash-lite` |
| **Type** | Local, in-process |
| **Entry point** | `agents/event_planner/agent.py` |
| **Tools** | `get_public_holidays` (Nager.Date API), `GoogleSearchTool` |

**Responsibilities:** Recommends the optimal date for a community meetup by cross-referencing public holidays, local tech event calendars, and calendar policy rules.

**Scheduling rules:** No weekends, no Fridays, no public holidays, no bridge days around holidays, no late December. Prefers Tuesday–Thursday evenings (17:30–18:00 start). Searches Luma and Meetup.com for existing local events to avoid conflicts.

**Output:** 1–2 recommended dates with reasoning, conflict check, and holiday check.

---

## agenda_generator — Agenda Formatter

| | |
|:---|:---|
| **Model** | `gemini-3.5-flash-lite` |
| **Type** | Local, in-process |
| **Entry point** | `agents/agenda_generator/agent.py` |
| **Tools** | None (pure generation) |

**Responsibilities:** Generates a structured, copy-pasteable plain-text event agenda from speaker inputs with dynamically computed timeslots.

**Key constraints:**
- Minimum 2 speakers required
- Fixed baseline: Registration 17:30, Opening 18:00, Talk 1 at 18:10
- Timeline math: talk durations + break duration → derived end times
- "Ugly time" correction: rounds to nearest clean 5/10-minute interval by adjusting break length (minimum 20 minutes unless user overrides)
- Output is plain text, no Markdown formatting — suitable for direct paste into Meetup or Luma

---

## office_secretary — Office Secretary

| | |
|:---|:---|
| **Model** | `gemini-3.5-flash-lite` |
| **Type** | Local, in-process |
| **Entry point** | `agents/office_secretary/agent.py` |
| **Tools** | None (pure generation) |

**Responsibilities:** Drafts templated admin emails for two scenarios: temporary key card access for external visitors, and Event Hub space reservation for public events.

**Key constraints:**
- Refuses to generate email if date is not provided — no placeholder dates
- Default key access window: 16:00–21:00; default event time: 17:30–21:00
- Strictly uses provided visitor names and host name; does not invent details

---

## video_editor — Live Video Editor

| | |
|:---|:---|
| **Model (agent)** | `gemini-3.5-flash-lite` |
| **Model (outpaint)** | `gemini-3.1-flash-lite-image` |
| **Model (video)** | `veo-3.1-fast-generate-001` (default) or `gemini-omni-1.1-flash` |
| **Type** | Remote A2A microservice (private Cloud Run) |
| **Entry point** | `agents/video_editor/agent.py` |
| **Default port** | 8081 |
| **Tools** | `create_video_card` |

**Responsibilities:** Conversational speaker-card video editor. Collects speaker details and portrait media across multiple turns, then renders animated speaker card video(s).

**Pipeline:**
1. Portrait image → 9:16 outpainting via `gemini-3.1-flash-lite-image`
2. Outpainted image → cinematic video via Veo 3.1 or Gemini Omni Flash
3. Video → GSAP/HTML compositor → 1080p MP4, GIF, and/or 4K MP4

**Key constraints:**
- Does not call `create_video_card` until all required inputs are present: `talk_title`, `name`, `position_company`, and one portrait image or video
- Preserves draft state across turns; new uploaded media replaces only the media field
- Optionally proposes typo corrections before render, requires explicit user confirmation
- Ignores unrelated messages without modifying draft

**Auth:** All calls from root agent authenticated via OIDC Bearer token. Rejects unauthenticated requests.

**Evals:** Conversational contract eval suite (happy path, multi-turn draft persistence, unrelated-input rejection, typo gating) run against a deterministic render stub.

---

## receipt_scanner — Receipt Scanner

| | |
|:---|:---|
| **Model** | `gemini-3.7-flash` (multimodal OCR) |
| **Type** | Remote A2A microservice (private Cloud Run) |
| **Entry point** | `agents/receipt_scanner/agent.py` |
| **Default port** | 8082 |
| **Tools** | `read_receipt_file`, `get_usd_pln_rate`, `export_summary_to_google_docs` |

**Responsibilities:** Multimodal OCR extraction from receipt images and PDFs, multi-currency conversion, and Google Docs expense report generation.

**Pipeline:**
1. Native multimodal vision on attached images/PDFs (does not call `read_receipt_file` for chat attachments)
2. Extracts products, quantities, unit prices, taxes, totals, date, currency
3. Fetches live PLN/USD exchange rates from Pekao Bank and NBP APIs
4. Exports formatted expense report to a user-supplied Google Drive folder using a Docs template

**Google Drive integration:** Uses service account ADC workload identity (`GOOGLE_AUTH_METHOD=adc`). User must share their Drive folder with the SA email (`community-studio-runtime@<project>.iam.gserviceaccount.com`). Falls back to local `.docx` if Drive is unconfigured.

**Auth:** All calls from root agent authenticated via OIDC Bearer token.

**Evals:** Pinned real-world receipt image fixtures + deterministic currency conversion cases. See `docs/receipt_scanner_evals.md`.
