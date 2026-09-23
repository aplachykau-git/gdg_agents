import os
import unittest
from unittest.mock import patch

from agents.gemini_config import DEFAULT_IMAGE_MODEL, DEFAULT_MODEL, model_for


class TestModelConfig(unittest.TestCase):
    def test_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(model_for("video_editor"), DEFAULT_MODEL)

    def test_global_override_applies_to_text_roles_only(self):
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-x"}, clear=True):
            self.assertEqual(model_for("root_agent"), "gemini-x")
            self.assertEqual(model_for("video_outpaint", default=DEFAULT_IMAGE_MODEL), DEFAULT_IMAGE_MODEL)

    def test_role_override_beats_legacy_and_global(self):
        env = {"MODEL_VIDEO_PROMPT_DIRECTOR": "a", "VIDEO_PROMPT_DIRECTOR_MODEL": "b", "GEMINI_MODEL": "c"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(model_for("video_prompt_director", legacy_env="VIDEO_PROMPT_DIRECTOR_MODEL"), "a")
        with patch.dict(os.environ, {"VIDEO_PROMPT_DIRECTOR_MODEL": "b", "GEMINI_MODEL": "c"}, clear=True):
            self.assertEqual(model_for("video_prompt_director", legacy_env="VIDEO_PROMPT_DIRECTOR_MODEL"), "b")

    def test_every_agent_uses_the_config(self):
        from agents.agenda_generator.agent import agenda_agent
        from agents.event_planner.agent import planner_agent
        from agents.linkedin_post_generator.agent import linkedin_agent
        from agents.office_secretary.agent import office_agent
        from agents.registration_manager.agent import registration_agent
        from agents.video_editor.agent import video_editor_agent

        for agent in (
            agenda_agent,
            planner_agent,
            linkedin_agent,
            office_agent,
            registration_agent,
            video_editor_agent,
        ):
            self.assertIsInstance(agent.model, str)


if __name__ == "__main__":
    unittest.main()
