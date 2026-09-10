import os
import unittest
from unittest.mock import MagicMock, patch

from agents.video_editor.prompt_director import (
    FORBIDDEN_TERMS,
    _build_fallback_scenarios,
    format_scenarios_markdown,
    generate_creative_scenarios,
)
from agents.video_editor.tools.video_card_tool import create_video_card
from agents.video_editor.workflow_models import CreativeScenario, VideoEditorDraft, VideoShot


class FakeInlineData:
    def __init__(self, mime_type: str, data: bytes):
        self.mime_type = mime_type
        self.data = data


class FakePart:
    def __init__(self, text: str | None = None, inline_data: FakeInlineData | None = None):
        self.text = text
        self.inline_data = inline_data


class FakeContent:
    def __init__(self, parts: list[FakePart]):
        self.parts = parts


class FakeEvent:
    def __init__(self, event_id: str, parts: list[FakePart]):
        self.id = event_id
        self.author = "user"
        self.content = FakeContent(parts)


class FakeSession:
    def __init__(self, events: list[FakeEvent]):
        self.id = "test-session"
        self.events = events


class FakeToolContext:
    def __init__(self, state: dict, events: list[FakeEvent]):
        self.state = state
        self.session = FakeSession(events)


class TestPromptDirector(unittest.TestCase):
    def test_fallback_scenarios_structure_and_shots(self):
        scenarios = _build_fallback_scenarios("Autonomous Multi-Agent AI", "Alex Rivera")
        self.assertEqual(len(scenarios), 3)

        for sc in scenarios:
            self.assertTrue(sc.id)
            self.assertTrue(sc.title)
            self.assertTrue(sc.genre)
            self.assertTrue(sc.omni_prompt)
            self.assertEqual(len(sc.shots), 5, "Each scenario must have exactly 5 shots")

            expected_timings = [
                "00:00 - 00:02",
                "00:02 - 00:04",
                "00:04 - 00:06",
                "00:06 - 00:08",
                "00:08 - 00:10",
            ]
            for idx, shot in enumerate(sc.shots):
                self.assertEqual(shot.shot_number, idx + 1)
                self.assertEqual(shot.time_range, expected_timings[idx])
                self.assertTrue(shot.action)
                self.assertTrue(shot.camera)
                self.assertTrue(shot.lighting_atmosphere)

    def test_no_public_speaking_terms_in_scenarios(self):
        scenarios = _build_fallback_scenarios("Scaling Cloud Infrastructure", "Elena Rostova")
        for sc in scenarios:
            combined_text = (
                f"{sc.title} {sc.concept} {sc.omni_prompt} "
                + " ".join(f"{s.action} {s.camera} {s.lighting_atmosphere}" for s in sc.shots)
            ).lower()
            for forbidden in FORBIDDEN_TERMS:
                self.assertNotIn(
                    forbidden,
                    combined_text,
                    f"Forbidden public speaking term '{forbidden}' detected in scenario {sc.id}",
                )

    def test_format_scenarios_markdown(self):
        scenarios = _build_fallback_scenarios("Cybernetic Vision Systems", "Dr. Vance")
        md = format_scenarios_markdown(scenarios)
        self.assertIn("### 🎬 Creative Video Scenarios (5 shots × 2s each)", md)
        self.assertIn("Option 1:", md)
        self.assertIn("Shot 1", md)
        self.assertIn("Shot 5", md)
        self.assertIn("Omni Prompt", md)

    @patch("agents.video_editor.prompt_director.get_gemini_client")
    def test_generate_creative_scenarios_invokes_gemini_3_5_flash(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        scenarios = generate_creative_scenarios(
            talk_title="Quantum Computing in Practice",
            speaker_name="Sarah Jenkins",
            position_company="Chief Scientist, Q-Labs",
            speaker_bio="Expert in fault-tolerant qubits and quantum circuits.",
        )
        self.assertEqual(len(scenarios), 3)
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs.get("model"), "gemini-3.5-flash")
        config = call_kwargs.get("config")
        self.assertEqual(config.temperature, 1.35)

    @patch("agents.video_editor.prompt_director.get_gemini_client")
    def test_omni_prompt_synthesizes_shot_timings_when_missing(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = None

        from agents.video_editor.prompt_director import _RawGeneratedScenarios

        raw_sc = CreativeScenario(
            id="scenario_test",
            title="The Signal Tuner",
            genre="Analog Retro-Futurism",
            concept="Tuning chaotic frequencies into a single beam.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="Dominika approaches the CRT monitor.",
                    camera="Slow push-in.",
                    lighting_atmosphere="Green phosphorescent glow.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="She turns the copper knob.",
                    camera="Macro close-up.",
                    lighting_atmosphere="Amber spark reflections.",
                ),
            ],
            omni_prompt="A retro-futuristic sequence with Dominika turning knobs without explicit timestamps.",
        )
        mock_response.parsed = _RawGeneratedScenarios(scenarios=[raw_sc])
        mock_client.models.generate_content.return_value = mock_response

        scenarios = generate_creative_scenarios(
            talk_title="Signal Processing",
            speaker_name="Dominika Zając",
        )
        self.assertEqual(len(scenarios), 1)
        self.assertIn("00:00 - 00:02", scenarios[0].omni_prompt)
        self.assertIn("00:02 - 00:04", scenarios[0].omni_prompt)
        self.assertIn("Shot 1", scenarios[0].omni_prompt)
        self.assertIn("Shot 2", scenarios[0].omni_prompt)


class TestCreateVideoCardWithScenarioSelection(unittest.IsolatedAsyncioTestCase):
    @patch("agents.video_editor.tools.video_card_tool.generate_creative_scenarios")
    async def test_proposes_scenarios_when_image_provided_without_direction(self, mock_gen_scenarios):
        fake_upload = FakePart(
            inline_data=FakeInlineData(
                mime_type="image/png",
                data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82",
            )
        )
        context = FakeToolContext(
            state={},
            events=[FakeEvent("evt-1", [fake_upload])],
        )

        mock_gen_scenarios.return_value = _build_fallback_scenarios("Microservices in Space", "Commander Mark")

        with patch.dict("os.environ", {"ENABLE_VIDEO_GENERATION": "true"}):
            result = await create_video_card(
                talk_title="Microservices in Space",
                name="Commander Mark",
                position_company="Space Station Alpha",
                media_type="image",
                tool_context=context,
            )

        self.assertEqual(result["status"], "awaiting_confirmation")
        self.assertEqual(result["requested_action"], "select_scenario")
        self.assertTrue(len(result["scenarios"]) >= 3)
        self.assertIn("🎬 Creative Video Scenarios", result["message"])

    async def test_selects_single_scenario_and_proceeds(self):
        fake_upload = FakePart(
            inline_data=FakeInlineData(
                mime_type="image/png",
                data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82",
            )
        )
        scenarios = _build_fallback_scenarios("Microservices in Space", "Commander Mark")
        context = FakeToolContext(
            state={
                "video_editor_draft": {
                    "title": "Microservices in Space",
                    "name": "Commander Mark",
                    "position_company": "Space Station Alpha",
                    "suggested_scenarios": [s.model_dump() for s in scenarios],
                }
            },
            events=[FakeEvent("evt-1", [fake_upload])],
        )

        with patch("agents.video_editor.tools.video_card_tool.render_video_card") as mock_render:
            mock_render.return_value = MagicMock(assets=[])
            with patch("agents.video_editor.tools.video_card_tool.confirmation_required", return_value=False):
                result = await create_video_card(
                    talk_title="Microservices in Space",
                    name="Commander Mark",
                    position_company="Space Station Alpha",
                    media_type="image",
                    selected_scenario_id=scenarios[0].id,
                    tool_context=context,
                )
                self.assertEqual(result["status"], "success")
                mock_render.assert_called_once()
                draft_arg = mock_render.call_args[0][0]
                self.assertEqual(draft_arg.selected_scenario_id, scenarios[0].id)
                self.assertTrue(draft_arg.creative_direction)
                self.assertIn("Shot 1", draft_arg.creative_direction)

    async def test_render_blocked_until_scenario_is_selected(self):
        fake_upload = FakePart(
            inline_data=FakeInlineData(
                mime_type="image/png",
                data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82",
            )
        )
        scenarios = _build_fallback_scenarios("Microservices in Space", "Commander Mark")
        context = FakeToolContext(
            state={
                "video_editor_draft": {
                    "title": "Microservices in Space",
                    "name": "Commander Mark",
                    "position_company": "Space Station Alpha",
                    "suggested_scenarios": [s.model_dump() for s in scenarios],
                }
            },
            events=[FakeEvent("evt-1", [fake_upload])],
        )

        with patch("agents.video_editor.tools.video_card_tool.render_video_card") as mock_render:
            result = await create_video_card(
                talk_title="Microservices in Space",
                name="Commander Mark",
                position_company="Space Station Alpha",
                media_type="image",
                confirm_render=True,
                tool_context=context,
            )
            self.assertEqual(result["status"], "awaiting_confirmation")
            self.assertEqual(result["requested_action"], "select_scenario")
            mock_render.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
