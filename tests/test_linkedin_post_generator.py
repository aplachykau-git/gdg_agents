"""
Unit and Integration Tests for LinkedIn Post Generator Agent.
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

from agents.linkedin_post_generator.agent import linkedin_agent


class TestLinkedInPostGeneratorAgent(unittest.TestCase):
    """Unit tests for LinkedIn Post Generator agent properties and dynamics."""

    def test_linkedin_agent_structure(self):
        self.assertIsNotNone(linkedin_agent)
        self.assertEqual(linkedin_agent.name, "linkedin_post_generator")
        self.assertEqual(linkedin_agent.tools, [])

    def test_community_name_environment_variable(self):
        with patch.dict(os.environ, {"GDG_COMMUNITY_NAME": "Berlin"}):
            import importlib

            import agents.linkedin_post_generator.agent as li_mod

            importlib.reload(li_mod)

            self.assertIn("#GDGBerlin", li_mod.linkedin_agent.instruction)

        # Restore default
        with patch.dict(os.environ, {"GDG_COMMUNITY_NAME": "Krakow"}):
            importlib.reload(li_mod)


class TestLinkedInPostGeneratorIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration and Runner tests for LinkedIn Post Generator."""

    async def test_linkedin_runner_session_creation(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="linkedin_generator_test",
            agent=linkedin_agent,
            session_service=session_service,
            auto_create_session=True,
        )
        self.assertIsNotNone(runner)

        session = await session_service.create_session(
            user_id="test_organizer",
            session_id="li_sess_01",
            app_name="linkedin_generator_test",
        )
        self.assertIsNotNone(session)
        self.assertEqual(session.id, "li_sess_01")

    async def test_linkedin_runner_execution_flow(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="linkedin_generator_test",
            agent=linkedin_agent,
            session_service=session_service,
            auto_create_session=True,
        )

        sample_linkedin_output = (
            "### Variant 1: (The Architectural Perspective)\n\n"
            "Excited to welcome @Alice Smith to the stage at our upcoming meetup!\n"
            "We'll explore how modern multi-agent workflows are built.\n\n"
            "Join us to secure your spot!\n"
            "#GDGKrakow #AI #Agents #TechMeetup\n\n"
            "### Variant 2: (The Community Focus)\n\n"
            "Ready to dive deep into AI systems? @Alice Smith is joining us to share insights.\n\n"
            "See you there!\n"
            "#GDGKrakow #AI #SoftwareEngineering #GDG"
        )

        mock_event = MagicMock()
        mock_event.content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=sample_linkedin_output)],
        )

        async def fake_run_async(*args, **kwargs):
            yield mock_event

        with patch.object(runner, "run_async", side_effect=fake_run_async):
            events = []
            prompt = (
                "Generate LinkedIn post for speaker:\n"
                "Speaker: Alice Smith\n"
                "Bio: Staff Engineer at TechCorp\n"
                "Talk Title: Architectural Patterns for Autonomous Agents\n"
                "Description: In-depth exploration of agentic design patterns and resilient tool calling."
            )
            async for event in runner.run_async(
                user_id="test_organizer",
                session_id="li_sess_02",
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ):
                events.append(event)

            self.assertEqual(len(events), 1)
            response_text = events[0].content.parts[0].text
            self.assertIn("### Variant 1:", response_text)
            self.assertIn("### Variant 2:", response_text)
            self.assertIn("#GDGKrakow", response_text)
            self.assertIn("@Alice Smith", response_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
