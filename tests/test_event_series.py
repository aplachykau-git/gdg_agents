"""The Build with AI / DevFest switch from the settings drives the LinkedIn and agenda texts."""

import os
import unittest
from unittest.mock import patch

from agents.agenda_generator.agent import agenda_agent
from agents.common.event_series import CITY_TOKEN, city_from_state, city_hashtag, default_city, series_from_state
from agents.event_planner.agent import planner_agent
from agents.linkedin_post_generator.agent import linkedin_agent
from agents.office_secretary.agent import office_agent
from agents.video_editor.tools.composer_tools import apply_devfest_city
from agents.video_editor.video_card_service import RenderSettings
from tests.agent_harness import AgentHarness, text


def system_instruction(harness: AgentHarness) -> str:
    return str(harness.llm.requests[-1].config.system_instruction)


class TestSeriesSelection(unittest.TestCase):
    def test_reads_both_key_spellings_and_defaults(self):
        self.assertEqual(series_from_state({}).name, "Build with AI")
        self.assertEqual(series_from_state({"video_template": "devfest"}).name, "DevFest")
        self.assertEqual(series_from_state({"videoTemplate": "devfest"}).name, "DevFest")
        self.assertEqual(series_from_state({"video_template": "unknown"}).name, "Build with AI")

    def test_city_from_settings(self):
        self.assertEqual(city_from_state({"community_name": "GDG Krakow"}, "Community"), "Krakow")
        self.assertEqual(city_from_state({}, "Krakow"), "Krakow")
        self.assertEqual(city_from_state({"communityName": "Wroclaw"}), "Wroclaw")

    def test_default_city_is_krakow(self):
        with patch.dict(os.environ, {"COMMUNITY_NAME": "", "GDG_COMMUNITY_NAME": ""}):
            self.assertEqual(default_city(), "Krakow")
            self.assertEqual(city_from_state({}), "Krakow")
        with patch.dict(os.environ, {"COMMUNITY_NAME": "Community"}):
            self.assertEqual(default_city(), "Krakow")
        with patch.dict(os.environ, {"COMMUNITY_NAME": "GDG Warsaw"}):
            self.assertEqual(default_city(), "Warsaw")

    def test_city_hashtag(self):
        self.assertEqual(city_hashtag("New York"), "NewYork")
        self.assertEqual(city_hashtag("Kraków"), "Kraków")


class TestAgentsFollowTheSetting(unittest.TestCase):
    def run_agent(self, agent, state):
        harness = AgentHarness(agent, initial_state=state).script(text("ok"))
        harness.say("go")
        return system_instruction(harness)

    def test_agenda_intro_devfest(self):
        instruction = self.run_agent(agenda_agent, {"video_template": "devfest", "community_name": "GDG Krakow"})
        self.assertIn("DevFest Krakow is part of DevFest", instruction)
        self.assertNotIn("Build with AI is a community-led event series", instruction)

    def test_agenda_intro_build_with_ai(self):
        instruction = self.run_agent(agenda_agent, {"video_template": "build_with_ai", "community_name": "GDG Krakow"})
        self.assertIn("Build with AI is a community-led event series in Krakow", instruction)
        self.assertNotIn("DevFest", instruction)

    def test_linkedin_devfest(self):
        instruction = self.run_agent(linkedin_agent, {"video_template": "devfest"})
        self.assertIn("#DevFest", instruction)
        self.assertNotIn("#BuildWithAI", instruction)

    def test_linkedin_build_with_ai(self):
        instruction = self.run_agent(linkedin_agent, {"videoTemplate": "build_with_ai"})
        self.assertIn("#BuildWithAI", instruction)
        self.assertNotIn("DevFest", instruction)


class TestCityFromSettings(unittest.TestCase):
    def run_agent(self, agent, state):
        harness = AgentHarness(agent, initial_state=state).script(text("ok"))
        harness.say("go")
        return system_instruction(harness)

    def test_linkedin_uses_city_hashtag(self):
        instruction = self.run_agent(linkedin_agent, {"community_name": "GDG Wroclaw", "video_template": "devfest"})
        self.assertIn("#GDGWroclaw", instruction)
        self.assertIn("DevFest Wroclaw", instruction)
        self.assertIn("GDG Wroclaw", instruction)
        self.assertNotIn("#GDGKrakow`", instruction)
        self.assertNotIn(CITY_TOKEN, instruction)
        self.assertNotIn("__COMMUNITY", instruction)

    def test_agenda_uses_city(self):
        instruction = self.run_agent(agenda_agent, {"community_name": "GDG Gdansk", "video_template": "devfest"})
        self.assertIn("DevFest Gdansk is part of DevFest", instruction)
        self.assertIn("GDG Gdansk Agenda Generator", instruction)

    def test_planner_searches_the_city(self):
        instruction = self.run_agent(planner_agent, {"community_name": "GDG Berlin"})
        self.assertIn("AI meetups luma", instruction)
        self.assertIn('"Berlin AI meetups luma', instruction)
        self.assertNotIn("__COMMUNITY", instruction)

    def test_office_secretary_name(self):
        instruction = self.run_agent(office_agent, {"community_name": "GDG Poznan"})
        self.assertIn("GDG Poznan Office Secretary", instruction)

    def test_city_changes_between_messages(self):
        harness = AgentHarness(linkedin_agent, initial_state={"community_name": "GDG Krakow"})
        harness.script(text("one"), text("two"))
        harness.say("first")
        self.assertIn("#GDGKrakow", system_instruction(harness))
        harness.say("second", state_delta={"community_name": "GDG Lodz"})
        self.assertIn("#GDGLodz", system_instruction(harness))


class TestDevFestCityPill(unittest.TestCase):
    PILL = '<rect id="krakow_pill" /><path id="krakow_text" d="M1 2Z" fill="#1E1E1E" />'

    def test_krakow_keeps_vector_glyphs(self):
        self.assertEqual(apply_devfest_city(self.PILL, "Krakow"), self.PILL)
        self.assertEqual(apply_devfest_city(self.PILL, None), self.PILL)

    def test_other_city_becomes_text(self):
        out = apply_devfest_city(self.PILL, "Wrocław & Co")
        self.assertIn('<text id="krakow_text"', out)
        self.assertIn("Wrocław &amp; Co</text>", out)
        self.assertNotIn("<path", out)

    def test_render_settings_read_city(self):
        ctx = type("Ctx", (), {"state": {"community_name": "GDG Katowice"}})()
        self.assertEqual(RenderSettings.from_tool_context(ctx).city, "Katowice")


if __name__ == "__main__":
    unittest.main()
