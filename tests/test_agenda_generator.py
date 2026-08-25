"""
Unit and Integration Tests for Agenda Generator Agent.
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

from agents.agenda_generator.agent import agenda_agent


class TestAgendaGeneratorAgent(unittest.TestCase):
    """Unit tests for Agenda Generator agent properties and dynamics."""

    def test_agenda_agent_structure(self):
        self.assertIsNotNone(agenda_agent)
        self.assertEqual(agenda_agent.name, "agenda_generator")
        self.assertEqual(agenda_agent.tools, [])

    def test_community_name_environment_variable(self):
        with patch.dict(os.environ, {"GDG_COMMUNITY_NAME": "Warsaw"}):
            import importlib

            import agents.agenda_generator.agent as ag_mod

            importlib.reload(ag_mod)

            self.assertIn("Warsaw", ag_mod.agenda_agent.instruction)

        # Restore default
        with patch.dict(os.environ, {"GDG_COMMUNITY_NAME": "Krakow"}):
            importlib.reload(ag_mod)


class TestAgendaGeneratorIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration and Runner tests for Agenda Generator."""

    async def test_agenda_runner_session_creation(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="agenda_generator_test",
            agent=agenda_agent,
            session_service=session_service,
            auto_create_session=True,
        )
        self.assertIsNotNone(runner)

        session = await session_service.create_session(
            user_id="test_organizer",
            session_id="agenda_sess_01",
            app_name="agenda_generator_test",
        )
        self.assertIsNotNone(session)
        self.assertEqual(session.id, "agenda_sess_01")

    async def test_agenda_runner_execution_flow(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="agenda_generator_test",
            agent=agenda_agent,
            session_service=session_service,
            auto_create_session=True,
        )

        sample_agenda_output = (
            "Here is the calculated agenda:\n\n"
            "### Agenda\n\n"
            "Build with AI is a GDG community-led event series in Krakow.\n\n"
            "AGENDA\n\n"
            "🎟️ 17:30 - Registration & Networking\n\n"
            "🚀 18:00 - Opening\n\n"
            "🎤 18:10 - Alice Smith - Building Multi-Agent Workflows\n\n"
            "🍕 18:50 - Break & Networking\n\n"
            "🎤 19:10 - Bob Jones - Vector Databases in Production\n\n"
            "REGISTRATION ❗\n"
            "Please register on this page (RSVP), and bring your ID with you."
        )

        mock_event = MagicMock()
        mock_event.content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=sample_agenda_output)],
        )

        async def fake_run_async(*args, **kwargs):
            yield mock_event

        with patch.object(runner, "run_async", side_effect=fake_run_async):
            events = []
            prompt = (
                "Create agenda for 2 speakers:\n"
                "1. Alice Smith - Building Multi-Agent Workflows (40 min)\n"
                "2. Bob Jones - Vector Databases in Production (40 min)\n"
                "Break: 20 min"
            )
            async for event in runner.run_async(
                user_id="test_organizer",
                session_id="agenda_sess_02",
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ):
                events.append(event)

            self.assertEqual(len(events), 1)
            response_text = events[0].content.parts[0].text
            self.assertIn("17:30 - Registration & Networking", response_text)
            self.assertIn("18:10 - Alice Smith", response_text)
            self.assertIn("18:50 - Break & Networking", response_text)
            self.assertIn("19:10 - Bob Jones", response_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
