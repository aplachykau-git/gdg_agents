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
        self.assertEqual(len(scenarios), 5)

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
        self.assertIn("Option 5:", md)
        self.assertIn("Shot 1", md)
        self.assertIn("Shot 5", md)
        self.assertIn("Omni Prompt", md)

    @patch("agents.video_editor.genre_scout.get_gemini_client")
    @patch("agents.video_editor.prompt_director.get_gemini_client")
    def test_generate_creative_scenarios_two_stage_pipeline(self, mock_director_client, mock_scout_client):
        # Stage 1 Scout mock
        scout_client = MagicMock()
        mock_scout_client.return_value = scout_client
        scout_response = MagicMock()
        scout_response.parsed = None
        scout_response.text = (
            '{"genres": ['
            '{"id": "noir_1", "title": "Noir Investigation", "genre": "Film Noir", "visual_universe": "Rainy alleyways", "aesthetic_manifesto": "Shadows", "narrative_metaphor": "Searching clues"},'
            '{"id": "solar_2", "title": "Solar Utopian", "genre": "Solarpunk", "visual_universe": "Sunlit glass greenhouse", "aesthetic_manifesto": "Warm light", "narrative_metaphor": "Growing plants"},'
            '{"id": "pop_3", "title": "Pastel Whimsy", "genre": "Pop-Art Symmetrical", "visual_universe": "Mint and coral diorama", "aesthetic_manifesto": "Symmetry", "narrative_metaphor": "Tuning gears"},'
            '{"id": "steam_4", "title": "Clockwork Basework", "genre": "Constructivist Steampunk", "visual_universe": "Subterranean gears", "aesthetic_manifesto": "Steam chiaroscuro", "narrative_metaphor": "Turning massive gears"},'
            '{"id": "sport_5", "title": "Sunrise Velocity", "genre": "Sports Anthem", "visual_universe": "Misty bridge run", "aesthetic_manifesto": "Golden flare", "narrative_metaphor": "High-velocity sprint"}'
            "]}"
        )
        scout_client.models.generate_content.return_value = scout_response

        # Stage 2 Director mock
        director_client = MagicMock()
        mock_director_client.return_value = director_client
        director_response = MagicMock()
        director_response.parsed = None
        director_response.text = None  # Fallback to _build_scenarios_from_genres
        director_client.models.generate_content.return_value = director_response

        scenarios = generate_creative_scenarios(
            talk_title="Quantum Computing in Practice",
            speaker_name="Sarah Jenkins",
            position_company="Chief Scientist, Q-Labs",
            speaker_bio="Expert in fault-tolerant qubits and quantum circuits.",
        )
        self.assertEqual(len(scenarios), 5)
        # Stage 1 called
        scout_client.models.generate_content.assert_called_once()
        scout_kwargs = scout_client.models.generate_content.call_args.kwargs
        self.assertEqual(scout_kwargs.get("model"), "gemini-3.8-flash")
        self.assertEqual(scout_kwargs.get("config").temperature, 1.6)

        # Stage 2 called concurrently for each of the 5 genres
        self.assertEqual(director_client.models.generate_content.call_count, 5)
        director_kwargs = director_client.models.generate_content.call_args.kwargs
        self.assertEqual(director_kwargs.get("model"), "gemini-3.8-flash")
        self.assertEqual(director_kwargs.get("config").temperature, 1.2)

        # Confirm scenarios inherited genres from Stage 1
        self.assertEqual(scenarios[0].genre, "Film Noir")
        self.assertEqual(scenarios[1].genre, "Solarpunk")
        self.assertEqual(scenarios[2].genre, "Pop-Art Symmetrical")
        self.assertEqual(scenarios[3].genre, "Constructivist Steampunk")
        self.assertEqual(scenarios[4].genre, "Sports Anthem")

    @patch("agents.video_editor.prompt_director.get_gemini_client")
    def test_direct_scenarios_from_genres_invokes_gemini_3_8_flash(self, mock_get_client):
        from agents.video_editor.genre_scout import GenreBrief
        from agents.video_editor.prompt_director import direct_scenarios_from_genres

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = None
        mock_client.models.generate_content.return_value = mock_response

        briefs = [
            GenreBrief(
                id="cyber_1",
                title="Neon City Heist",
                genre="Cyberpunk Thriller",
                visual_universe="Rain on neon glass",
                aesthetic_manifesto="Anamorphic flares",
                narrative_metaphor="Infiltrating secure networks",
            )
        ]

        scenarios = direct_scenarios_from_genres(
            genres=briefs,
            talk_title="Distributed Systems",
            speaker_name="Alex Rivera",
        )
        self.assertEqual(len(scenarios), 1)
        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(call_kwargs.get("model"), "gemini-3.8-flash")
        config = call_kwargs.get("config")
        self.assertEqual(config.temperature, 1.2)
        self.assertEqual(scenarios[0].genre, "Cyberpunk Thriller")

    @patch("agents.video_editor.prompt_director.get_gemini_client")
    def test_omni_prompt_synthesizes_shot_timings_when_missing(self, mock_get_client):
        from agents.video_editor.genre_scout import GenreBrief
        from agents.video_editor.prompt_director import _RawGeneratedScenarios, direct_scenarios_from_genres

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = None

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

        briefs = [
            GenreBrief(
                id="retro_1",
                title="The Signal Tuner",
                genre="Analog Retro-Futurism",
                visual_universe="CRT monitors and copper knobs",
                aesthetic_manifesto="Phosphorescent glow",
                narrative_metaphor="Tuning signals",
            )
        ]
        scenarios = direct_scenarios_from_genres(
            genres=briefs,
            talk_title="Signal Processing",
            speaker_name="Dominika Zając",
        )
        self.assertEqual(len(scenarios), 1)
        self.assertIn("00:00 - 00:02", scenarios[0].omni_prompt)
        self.assertIn("00:02 - 00:04", scenarios[0].omni_prompt)
        self.assertIn("Shot 1", scenarios[0].omni_prompt)
        self.assertIn("Shot 2", scenarios[0].omni_prompt)


class TestGenreScout(unittest.TestCase):
    def test_sample_creative_archetypes_returns_distinct_clusters(self):
        from agents.video_editor.genre_scout import sample_creative_archetypes

        samples = sample_creative_archetypes(count=5)
        self.assertEqual(len(samples), 5)
        names = [s["name"] for s in samples]
        self.assertEqual(len(set(names)), 5, "Sampled archetypes must be unique")

    @patch("agents.video_editor.genre_scout.get_gemini_client")
    def test_scout_creative_genres_calls_gemini_with_high_entropy(self, mock_get_client):
        from agents.video_editor.genre_scout import scout_creative_genres

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = (
            '{"genres": ['
            '{"id": "french_wave", "title": "Café Concurrency", "genre": "1960s French New Wave", "visual_universe": "Parisian cafe", "aesthetic_manifesto": "Handheld 35mm", "narrative_metaphor": "Debating algorithms"},'
            '{"id": "german_exp", "title": "Shadow Pipeline", "genre": "1920s German Expressionism", "visual_universe": "Angular shadows", "aesthetic_manifesto": "Chiaroscuro", "narrative_metaphor": "Architecting systems"},'
            '{"id": "mtv_grunge", "title": "Distorted Data", "genre": "90s MTV Mixed-Media", "visual_universe": "Paper cutout collage", "aesthetic_manifesto": "Fisheye", "narrative_metaphor": "Fast sorting"},'
            '{"id": "solar_prism", "title": "Solar Cathedral", "genre": "Visionary Solarpunk", "visual_universe": "Crystal greenhouse", "aesthetic_manifesto": "Prismatic caustics", "narrative_metaphor": "Harvesting photons"},'
            '{"id": "steam_dynamo", "title": "Iron Dynamo", "genre": "Constructivist Steampunk", "visual_universe": "Subterranean gears", "aesthetic_manifesto": "Furnace chiaroscuro", "narrative_metaphor": "Turning massive flywheels"}'
            "]}"
        )
        mock_client.models.generate_content.return_value = mock_response

        briefs = scout_creative_genres(
            talk_title="Modern Concurrency",
            speaker_name="Jan Kowalski",
        )
        self.assertEqual(len(briefs), 5)
        mock_client.models.generate_content.assert_called_once()
        kwargs = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(kwargs.get("model"), "gemini-3.8-flash")
        self.assertEqual(kwargs.get("config").temperature, 1.6)
        self.assertEqual(briefs[0].genre, "1960s French New Wave")
        self.assertEqual(briefs[1].genre, "1920s German Expressionism")
        self.assertEqual(briefs[2].genre, "90s MTV Mixed-Media")
        self.assertEqual(briefs[3].genre, "Visionary Solarpunk")
        self.assertEqual(briefs[4].genre, "Constructivist Steampunk")


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


class TestMetadataReviewFallback(unittest.IsolatedAsyncioTestCase):
    async def test_review_metadata_falls_back_to_local_validation_on_error(self):
        from agents.video_editor.video_card_service import _review_metadata
        from agents.video_editor.workflow import StructuredResponseError, ValidatedMetadata

        metadata = ValidatedMetadata(
            title="Building DevFest with AI",
            name="Yuliya Aplachykava",
            position_company="Designer, EPAM Systems",
        )
        with patch(
            "agents.video_editor.workflow._structured_response",
            side_effect=StructuredResponseError("Service unavailable"),
        ):
            # Should fall back to approving the valid metadata instead of failing with model_unavailable
            failure = await _review_metadata(metadata)
            self.assertIsNone(failure, "Valid metadata should be approved when review model is unavailable")


class TestAnonymousPromptSanitization(unittest.TestCase):
    def test_compile_creative_prompt_replaces_speaker_name_with_protagonist(self):
        from agents.video_editor.video_card_service import compile_creative_prompt

        draft = VideoEditorDraft(
            title="Building DevFest with AI",
            name="Yuliya Aplachykava",
            position_company="Designer, EPAM Systems",
            creative_direction=(
                "Shot 1 (00:00 - 00:02): Yuliya Aplachykava enters the world. "
                "Shot 2 (00:02 - 00:04): yuliya taps a call bell. "
                "Shot 3 (00:04 - 00:06): At the center, Yuliya Aplachykava maneuvers gears."
            ),
        )
        prompt = compile_creative_prompt(draft)
        self.assertNotIn("Yuliya", prompt)
        self.assertNotIn("yuliya", prompt)
        self.assertNotIn("Aplachykava", prompt)
        self.assertIn("The protagonist", prompt)
        self.assertIn("the protagonist", prompt.lower())

    def test_fallback_scenarios_have_no_real_names(self):
        from agents.video_editor.prompt_director import _build_fallback_scenarios

        scenarios = _build_fallback_scenarios("Building DevFest with AI", "Yuliya Aplachykava")
        for sc in scenarios:
            for shot in sc.shots:
                self.assertNotIn("Yuliya", shot.action)
                self.assertNotIn("Aplachykava", shot.action)
            self.assertNotIn("Yuliya", sc.narrative_metaphor or "")
            self.assertNotIn("Aplachykava", sc.narrative_metaphor or "")

    def test_reorder_shots_and_rebuild_prompt(self):
        from agents.video_editor.prompt_director import reorder_shots_and_rebuild_prompt
        from agents.video_editor.workflow_models import VideoShot

        original_shots = [
            VideoShot(
                shot_number=1,
                time_range="00:00 - 00:02",
                action="Entering the misty street.",
                camera="Slow push",
                lighting_atmosphere="Amber glow",
            ),
            VideoShot(
                shot_number=2,
                time_range="00:02 - 00:04",
                action="Activating the generator.",
                camera="Pan right",
                lighting_atmosphere="Amber glow",
            ),
            VideoShot(
                shot_number=3,
                time_range="00:04 - 00:06",
                action="Gears engage at high speed.",
                camera="Close up",
                lighting_atmosphere="Amber glow",
            ),
        ]
        # Swap Shot 1 and Shot 3
        swapped = [original_shots[2], original_shots[1], original_shots[0]]
        reindexed, prompt = reorder_shots_and_rebuild_prompt(swapped, genre="Steampunk Mechanical")

        self.assertEqual(len(reindexed), 3)
        self.assertEqual(reindexed[0].shot_number, 1)
        self.assertEqual(reindexed[0].time_range, "00:00 - 00:02")
        self.assertEqual(reindexed[0].action, "Gears engage at high speed.")

        self.assertEqual(reindexed[2].shot_number, 3)
        self.assertEqual(reindexed[2].time_range, "00:04 - 00:06")
        self.assertEqual(reindexed[2].action, "Entering the misty street.")

        self.assertIn("Shot 1 (00:00 - 00:02): Gears engage at high speed.", prompt)
        self.assertIn("Shot 3 (00:04 - 00:06): Entering the misty street.", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
