"""
Unit and Integration Tests for Event Planner Agent and Tools.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(WORKSPACE_ROOT))

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from agents.event_planner.agent import planner_agent
from agents.event_planner.tools import get_public_holidays


class TestGetPublicHolidaysTool(unittest.TestCase):
    """Unit tests for the get_public_holidays tool function."""

    @patch("agents.event_planner.tools.requests.get")
    def test_get_public_holidays_success_mocked(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"date": "2026-01-01", "localName": "Nowy Rok", "name": "New Year's Day", "global": True, "extra": 123},
            {"date": "2026-05-01", "localName": "Święto Pracy", "name": "Labour Day", "global": True},
        ]
        mock_get.return_value = mock_response

        res = get_public_holidays(year=2026, country_code="PL")

        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("year"), 2026)
        self.assertEqual(res.get("country_code"), "PL")
        holidays = res.get("holidays", [])
        self.assertEqual(len(holidays), 2)
        self.assertEqual(holidays[0]["date"], "2026-01-01")
        self.assertEqual(holidays[0]["name"], "New Year's Day")
        self.assertNotIn("extra", holidays[0])

    @patch("agents.event_planner.tools.requests.get")
    def test_get_public_holidays_fallback_poland(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Network unavailable")

        res = get_public_holidays(year=2026, country_code="pl")

        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("source_fallback"))
        self.assertEqual(res.get("country_code"), "PL")
        holidays = res.get("holidays", [])
        self.assertGreater(len(holidays), 0)

        # Check key Polish holidays are in fallback
        holiday_names = [h["name"] for h in holidays]
        self.assertIn("New Year's Day", holiday_names)
        self.assertIn("Independence Day", holiday_names)
        self.assertIn("Christmas Day", holiday_names)

    @patch("agents.event_planner.tools.requests.get")
    def test_get_public_holidays_fallback_other_countries(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Timeout")

        res = get_public_holidays(year=2026, country_code="  de  ")

        self.assertTrue(res.get("success"))
        self.assertTrue(res.get("source_fallback"))
        self.assertEqual(res.get("country_code"), "DE")
        holidays = res.get("holidays", [])
        self.assertEqual(len(holidays), 2)
        holiday_names = [h["name"] for h in holidays]
        self.assertIn("New Year's Day", holiday_names)
        self.assertIn("Christmas Day", holiday_names)


class TestEventPlannerAgentIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration and Runner workflow tests for Event Planner agent."""

    async def test_event_planner_runner_initialization_and_session(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="event_planner_test",
            agent=planner_agent,
            session_service=session_service,
            auto_create_session=True,
        )
        self.assertIsNotNone(runner)

        session = await session_service.create_session(
            user_id="test_organizer",
            session_id="planner_sess_01",
            app_name="event_planner_test",
        )
        self.assertIsNotNone(session)
        self.assertEqual(session.id, "planner_sess_01")

    async def test_event_planner_runner_execution_flow(self):
        session_service = InMemorySessionService()
        runner = Runner(
            app_name="event_planner_test",
            agent=planner_agent,
            session_service=session_service,
            auto_create_session=True,
        )

        mock_event = MagicMock()
        mock_event.content = types.Content(
            role="model",
            parts=[types.Part.from_text(text="I recommend Tuesday, June 9, 2026 for the GDG meetup.")],
        )

        async def fake_run_async(*args, **kwargs):
            yield mock_event

        with patch.object(runner, "run_async", side_effect=fake_run_async):
            events = []
            async for event in runner.run_async(
                user_id="test_organizer",
                session_id="planner_sess_02",
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="Find the best meetup date for June 2026 in Krakow.")],
                ),
            ):
                events.append(event)

            self.assertEqual(len(events), 1)
            self.assertIn("Tuesday, June 9, 2026", events[0].content.parts[0].text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
