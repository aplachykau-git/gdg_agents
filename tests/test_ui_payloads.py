"""The structured "ui" contract that replaces regex parsing in the frontend."""

import datetime as dt
import unittest

from agents.agenda_generator.agent import agenda_agent
from agents.common import ui_payloads
from agents.event_planner.presentation import present_meetup_dates
from agents.linkedin_post_generator.agent import linkedin_agent
from agents.office_secretary.agent import office_agent
from agents.office_secretary.tools import present_email_draft
from tests.agent_harness import AgentHarness, call, text

POSTS = """Here are your posts.

### Variant 1: The Architect
🚀 Meet @Jane Doe, GDE at Example...

#GDGKrakow #AI #Android

### Variant 2: The Explorer
💻 Big news...

#GDGKrakow #Kotlin #AI

### Variant 3: The Community
🧠 Join us...

#GDGKrakow #Community #AI
"""

AGENDA = """Build with AI is a community-led event series in Krakow. This edition focuses on agents.

AGENDA

🎟️ 17:30 - Registration & Networking

🚀 18:00 - Opening

🎤 18:10 - Jane Doe - Agents in Production

🍕 18:50 - Break & Networking

🎤 19:10 - John Roe - Evals that matter

REGISTRATION ❗
Please register on this page (RSVP), and bring your ID with you.
"""


def next_weekday(weekday: int, weeks_ahead: int = 2) -> dt.date:
    today = dt.date.today()
    return today + dt.timedelta(days=(weekday - today.weekday()) % 7 + 7 * weeks_ahead)


class TestTextParsers(unittest.TestCase):
    def test_post_variants(self):
        payload = ui_payloads.parse_post_variants(POSTS)
        self.assertEqual(payload["type"], "post_variants")
        self.assertEqual([v["name"] for v in payload["variants"]], ["The Architect", "The Explorer", "The Community"])
        self.assertEqual(payload["intro"], "Here are your posts.")
        self.assertTrue(payload["variants"][0]["body"].startswith("🚀 Meet"))

    def test_plain_text_is_not_a_variant_card(self):
        self.assertIsNone(ui_payloads.parse_post_variants("Please send me the speaker bio."))

    def test_agenda(self):
        payload = ui_payloads.parse_agenda(AGENDA)
        self.assertEqual(payload["type"], "agenda")
        self.assertEqual([i["time"] for i in payload["items"]], ["17:30", "18:00", "18:10", "18:50", "19:10"])
        self.assertEqual(payload["items"][2]["title"], "Jane Doe - Agents in Production")
        self.assertEqual(payload["text"], AGENDA.strip())

    def test_question_about_agenda_is_not_an_agenda(self):
        self.assertIsNone(ui_payloads.parse_agenda("Which time should the agenda start, 17:30 - 18:00?"))

    def test_media_payload_classifies_assets(self):
        payload = ui_payloads.media(
            [
                {"label": "1080p MP4", "url": "https://x/card.mp4"},
                {"label": "4K MP4", "url": "https://x/card_4k.mp4"},
                {"label": "GIF", "url": "https://x/card.gif"},
                {"label": "Poster", "url": "https://x/card_poster.png"},
                {"label": "Avatar", "url": "https://x/card_avatar.png"},
                {"label": "Broken", "url": None, "availability": "unavailable"},
            ]
        )
        self.assertEqual(
            payload["urls"],
            {
                "video": "https://x/card.mp4",
                "video_4k": "https://x/card_4k.mp4",
                "gif": "https://x/card.gif",
                "poster": "https://x/card_poster.png",
                "avatar": "https://x/card_avatar.png",
            },
        )


class TestPresentationTools(unittest.TestCase):
    def test_email_draft(self):
        result = present_email_draft("Subject: Keys for visitors", "Hello team,\n...\nBest Regards")
        self.assertEqual(
            result["ui"],
            {
                "type": "email_draft",
                "subject": "Keys for visitors",
                "body": "Hello team,\n...\nBest Regards",
                "intro": "",
            },
        )

    def test_email_with_date_placeholder_is_rejected(self):
        result = present_email_draft("Keys", "Keys are needed on [Insert Date].")
        self.assertEqual(result["status"], "error")

    def test_meetup_dates_validation(self):
        wednesday, friday = next_weekday(2), next_weekday(4)
        result = present_meetup_dates(
            [{"date": wednesday.isoformat(), "reason": "mid-week"}], event_title="Build with AI"
        )
        self.assertEqual(result["ui"]["dates"][0]["weekday"], "Wednesday")
        self.assertEqual(result["ui"]["event_title"], "Build with AI")
        self.assertEqual(present_meetup_dates([{"date": friday.isoformat()}])["status"], "error")
        self.assertEqual(present_meetup_dates([{"date": "2020-01-08"}])["status"], "error")
        self.assertEqual(present_meetup_dates([{"date": "next Tuesday"}])["status"], "error")


class TestAgentsEmitPayloads(unittest.TestCase):
    """Real ADK runner + scripted model: the payload reaches the event stream the UI consumes."""

    def test_linkedin_text_gets_variants_metadata(self):
        harness = AgentHarness(linkedin_agent).script(text(POSTS))
        final = [e for e in harness.say("Write posts") if e.content and e.content.parts][-1]
        self.assertEqual(final.custom_metadata["ui"]["type"], "post_variants")

    def test_agenda_text_gets_agenda_metadata(self):
        harness = AgentHarness(agenda_agent).script(text(AGENDA))
        final = [e for e in harness.say("Make the agenda") if e.content and e.content.parts][-1]
        self.assertEqual(final.custom_metadata["ui"]["type"], "agenda")

    def test_clarifying_question_has_no_payload(self):
        harness = AgentHarness(agenda_agent).script(text("Who is the second speaker?"))
        final = [e for e in harness.say("Make the agenda") if e.content and e.content.parts][-1]
        self.assertFalse((final.custom_metadata or {}).get("ui"))

    def test_office_secretary_presents_email(self):
        harness = AgentHarness(office_agent).script(
            call("present_email_draft", subject="Temporary Access Request", body="Hello team,\n..."),
            text("Done - check the visitor names."),
        )
        responses = AgentHarness.tool_responses(harness.say("Keys for Anna on 14 October"), "present_email_draft")
        self.assertEqual(responses[0]["ui"]["type"], "email_draft")


if __name__ == "__main__":
    unittest.main(verbosity=2)
