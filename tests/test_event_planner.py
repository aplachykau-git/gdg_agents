"""
Unit and Integration Tests for Event Planner Agent and Tools.
"""

import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

WORKSPACE_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(WORKSPACE_ROOT))

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService

from agents.event_planner.agent import planner_agent
from agents.event_planner.tools import get_public_holidays
from tests.agent_harness import AgentHarness, call, text


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


class TestEventPlannerConversation(unittest.TestCase):
    """Real ADK runner + scripted model: the dates card comes from a validated tool result."""

    def test_rejects_weekend_and_presents_structured_dates(self):
        today = dt.date.today()
        wednesday = today + dt.timedelta(days=(2 - today.weekday()) % 7 + 14)
        saturday = wednesday + dt.timedelta(days=3)

        harness = AgentHarness(planner_agent)
        harness.script(
            call("present_meetup_dates", options=[{"date": saturday.isoformat(), "reason": "free evening"}]),
            call("present_meetup_dates", options=[{"date": wednesday.isoformat(), "reason": "mid-week"}]),
            text("Wednesday works best."),
        )
        responses = AgentHarness.tool_responses(harness.say("Find a date for our meetup"), "present_meetup_dates")

        self.assertEqual(responses[0]["status"], "error")
        self.assertIn("Saturday", responses[0]["message"])
        ui = responses[1]["ui"]
        self.assertEqual(ui["type"], "meetup_dates")
        self.assertEqual(ui["dates"][0]["date"], wednesday.isoformat())
        self.assertEqual(ui["dates"][0]["weekday"], "Wednesday")
        self.assertTrue(ui["dates"][0]["primary"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
