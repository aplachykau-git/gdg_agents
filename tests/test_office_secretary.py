"""
Unit and Integration Tests for Office Secretary Agent.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(WORKSPACE_ROOT))

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from agents.office_secretary.agent import office_agent


class TestOfficeSecretaryAgent(unittest.TestCase):
    """Unit tests for Office Secretary agent properties and instruction rules."""

    def test_office_agent_structure(self):
        self.assertIsNotNone(office_agent)
        self.assertEqual(office_agent.name, "office_secretary")
        self.assertEqual(office_agent.tools, [])


class TestOfficeSecretaryIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration and Runner tests for Office Secretary."""

    async def test_office_secretary_runner_session_creation(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="office_secretary_test",
            agent=office_agent,
            session_service=session_service,
            auto_create_session=True,
        )
        self.assertIsNotNone(runner)

        session = await session_service.create_session(
            user_id="test_organizer",
            session_id="office_sess_01",
            app_name="office_secretary_test",
        )
        self.assertIsNotNone(session)
        self.assertEqual(session.id, "office_sess_01")

    async def test_visitor_access_request_generation_flow(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="office_secretary_test",
            agent=office_agent,
            session_service=session_service,
            auto_create_session=True,
        )

        visitor_email_mock = (
            "Subject: Temporary Access Request for External Visitor(s)\n\n"
            "Hello team,\n"
            "We would like to request a key (keys) for external visitor(s):\n"
            "- John Doe\n"
            "- Jane Doe\n\n"
            "Keys are needed from 16:00 till 21:00 on June 15, 2026.\n"
            "I will be the host and return the keys.\n\n"
            "Thank you!\n"
            "Best Regards,\n"
            "Alex"
        )

        mock_event = MagicMock()
        mock_event.content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=visitor_email_mock)],
        )

        async def fake_run_async(*args, **kwargs):
            yield mock_event

        with patch.object(runner, "run_async", side_effect=fake_run_async):
            events = []
            prompt = (
                "Please draft a key access request for visitors John Doe and Jane Doe on June 15, 2026. Host is Alex."
            )
            async for event in runner.run_async(
                user_id="test_organizer",
                session_id="office_sess_02",
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ):
                events.append(event)

            self.assertEqual(len(events), 1)
            text = events[0].content.parts[0].text
            self.assertIn("Subject: Temporary Access Request", text)
            self.assertIn("John Doe", text)
            self.assertIn("June 15, 2026", text)

    async def test_event_hub_reservation_request_flow(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="office_secretary_test",
            agent=office_agent,
            session_service=session_service,
            auto_create_session=True,
        )

        hub_email_mock = (
            "Subject: Reservation Request for Event Hub - GDG AI Meetup #10\n\n"
            "Dear colleagues,\n"
            "we would like to request support and reserve space at Event Hub for the public event:\n\n"
            "GDG AI Meetup #10\n\n"
            "The date: June 15, 2026\n\n"
            "Format: Offline event w/o recording.\n"
            "Ticketing system: Bevy\n"
            "Time: 17:30 - 21:00\n\n"
            "For the help with event organisation:\n"
            "Keys are needed from 16:00 till 21:00 on June 15, 2026.\n"
            "I will be the host and return the keys.\n\n"
            "Thank you for your assistance.\n"
            "Regards,\n"
            "Alex"
        )

        mock_event = MagicMock()
        mock_event.content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=hub_email_mock)],
        )

        async def fake_run_async(*args, **kwargs):
            yield mock_event

        with patch.object(runner, "run_async", side_effect=fake_run_async):
            events = []
            prompt = "Reserve Event Hub for 'GDG AI Meetup #10' on June 15, 2026. Host is Alex."
            async for event in runner.run_async(
                user_id="test_organizer",
                session_id="office_sess_03",
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ):
                events.append(event)

            self.assertEqual(len(events), 1)
            text = events[0].content.parts[0].text
            self.assertIn("Reservation Request for Event Hub", text)
            self.assertIn("GDG AI Meetup #10", text)
            self.assertIn("June 15, 2026", text)

    async def test_missing_date_validation_refusal_flow(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="office_secretary_test",
            agent=office_agent,
            session_service=session_service,
            auto_create_session=True,
        )

        refusal_mock = (
            "I cannot generate this letter because the date is missing. "
            "Please provide the specific date for the visitor access."
        )

        mock_event = MagicMock()
        mock_event.content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=refusal_mock)],
        )

        async def fake_run_async(*args, **kwargs):
            yield mock_event

        with patch.object(runner, "run_async", side_effect=fake_run_async):
            events = []
            prompt = "Draft visitor access for John Doe without a date."
            async for event in runner.run_async(
                user_id="test_organizer",
                session_id="office_sess_04",
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ):
                events.append(event)

            self.assertEqual(len(events), 1)
            text = events[0].content.parts[0].text
            self.assertIn("date is missing", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
