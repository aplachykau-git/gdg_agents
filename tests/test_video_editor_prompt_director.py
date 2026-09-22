import os
import re
import unittest
from unittest.mock import MagicMock, patch

from agents.video_editor.prompt_director import (
    FORBIDDEN_TERMS,
    _build_fallback_scenarios,
    _clean_taxonomy_text,
    _ensure_scenario_styles,
    format_scenarios_markdown,
    format_timed_omni_prompt,
    generate_creative_scenarios,
    reorder_shots_and_rebuild_prompt,
)
from agents.video_editor.tools.media_tools import sanitize_i2v_prompt
from agents.video_editor.tools.video_card_tool import create_video_card
from agents.video_editor.workflow_models import CreativeScenario, ScenarioStyle, VideoEditorDraft, VideoShot


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
            use_taxonomy=False,
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
        self.assertEqual(director_kwargs.get("config").temperature, 1.5)

        # Confirm scenarios inherited genres from Stage 1
        self.assertEqual(scenarios[0].genre, "Film Noir")
        self.assertEqual(scenarios[1].genre, "Solarpunk")
        self.assertEqual(scenarios[2].genre, "Pop-Art Symmetrical")
        self.assertEqual(scenarios[3].genre, "Constructivist Steampunk")
        self.assertEqual(scenarios[4].genre, "Sports Anthem")

    @patch("agents.video_editor.prompt_director.get_gemini_client")
    def test_generate_creative_scenarios_with_taxonomy_database(self, mock_director_client):
        director_client = MagicMock()
        mock_director_client.return_value = director_client
        director_response = MagicMock()
        director_response.parsed = None
        director_response.text = None
        director_client.models.generate_content.return_value = director_response

        scenarios = generate_creative_scenarios(
            talk_title="Agentic Web Architectures",
            speaker_name="Alex Rivera",
            position_company="Lead Architect, DevCorp",
            speaker_bio="Specialist in distributed agents and WebMCP.",
            use_taxonomy=True,
        )
        self.assertEqual(len(scenarios), 5)
        for sc in scenarios:
            self.assertTrue(sc.id)
            self.assertTrue(sc.genre)
            self.assertIsNotNone(sc.style_profile)
            self.assertEqual(len(sc.shots), 5)
            self.assertEqual(len(sc.styles), 3)

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
        self.assertEqual(config.temperature, 1.5)
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
            use_taxonomy=False,
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

    def test_scout_creative_genres_uses_taxonomy_database_by_default(self):
        from agents.video_editor.genre_scout import scout_creative_genres

        briefs = scout_creative_genres(
            talk_title="Modern Concurrency",
            speaker_name="Jan Kowalski",
        )
        self.assertEqual(len(briefs), 5)
        for b in briefs:
            self.assertTrue(b.id)
            self.assertTrue(b.title)
            self.assertTrue(b.genre)
            self.assertTrue(b.visual_universe)
            self.assertTrue(b.aesthetic_manifesto)
            self.assertIsNotNone(b.style_profile)


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

    async def test_create_video_card_with_selected_style_id(self):
        fake_upload = FakePart(
            inline_data=FakeInlineData(
                mime_type="image/png",
                data=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82",
            )
        )
        from agents.video_editor.prompt_director import _ensure_scenario_styles

        scenarios = [
            _ensure_scenario_styles(s, i)
            for i, s in enumerate(_build_fallback_scenarios("Microservices in Space", "Commander Mark"), 1)
        ]
        style = scenarios[0].styles[0]
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
                    selected_scenario_id=style.id,
                    tool_context=context,
                )
                self.assertEqual(result["status"], "success")
                mock_render.assert_called_once()
                draft_arg = mock_render.call_args[0][0]
                self.assertEqual(draft_arg.selected_scenario_id, style.id)
                self.assertTrue(draft_arg.creative_direction)
                self.assertIn("Shot 1", draft_arg.creative_direction)

    async def test_create_video_card_with_option_number(self):
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
                    selected_scenario_id="Option 2",
                    tool_context=context,
                )
                self.assertEqual(result["status"], "success")
                mock_render.assert_called_once()
                draft_arg = mock_render.call_args[0][0]
                self.assertEqual(draft_arg.selected_scenario_id, scenarios[1].id)
                self.assertTrue(draft_arg.creative_direction)

    def test_compile_creative_prompt_resolves_from_suggested_scenarios_fallback(self):
        from agents.video_editor.prompt_director import _ensure_scenario_styles
        from agents.video_editor.video_card_service import compile_creative_prompt
        from agents.video_editor.workflow_models import VideoEditorDraft

        scenarios = [
            _ensure_scenario_styles(s, i)
            for i, s in enumerate(_build_fallback_scenarios("Microservices in Space", "Commander Mark"), 1)
        ]
        draft = VideoEditorDraft(
            title="Microservices in Space",
            name="Commander Mark",
            position_company="Space Station Alpha",
            creative_direction=None,
            selected_scenario_id=scenarios[2].styles[0].id,
            suggested_scenarios=scenarios,
        )
        prompt = compile_creative_prompt(draft)
        self.assertNotIn("Cinematic conference speaker portrait in a modern professional setting", prompt)
        self.assertIn("Shot 1", prompt)

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

    def test_ensure_scenario_styles_diversity_and_repetition_removal(self):
        # 1. Verify that options 1..5 receive distinct grounded and dynamic presets
        style2_names = []
        style3_names = []
        for i in range(1, 6):
            sc = CreativeScenario(
                id=f"scenario_{i}",
                title=f"Option {i}",
                genre=f"Genre {i}",
                concept=f"Concept for option {i}",
                omni_prompt=f"Omni prompt {i}",
                shots=[],
                number=i,
            )
            _ensure_scenario_styles(sc, idx=i)
            self.assertEqual(len(sc.styles), 3)
            style2_names.append(sc.styles[1].name)
            style3_names.append(sc.styles[2].name)

        # All 5 options must have unique style 2 and style 3 names
        self.assertEqual(len(set(style2_names)), 5, f"Duplicate style 2 names: {style2_names}")
        self.assertEqual(len(set(style3_names)), 5, f"Duplicate style 3 names: {style3_names}")

        # 2. Verify that if an LLM returns generic/repeated names on option 2, it gets replaced
        sc_repeated = CreativeScenario(
            id="noir_whisper",
            title="Noir Echoes",
            genre="Atmospheric Noir",
            concept="A dark rainy street investigation.",
            omni_prompt="Shot 1...",
            shots=[],
            number=2,
            styles=[
                ScenarioStyle(id="s1", name="Noir Signature", genre="Atmospheric Noir", omni_prompt="..."),
                ScenarioStyle(
                    id="s2",
                    name="Clean Modern Tech / Studio Commercial",
                    genre="Clean Modern Tech",
                    omni_prompt="...",
                ),
                ScenarioStyle(
                    id="s3",
                    name="Dynamic Cinematic Realism / Contrasting Movement",
                    genre="Cinematic Realism",
                    omni_prompt="...",
                ),
            ],
        )
        _ensure_scenario_styles(sc_repeated, idx=2)
        # Should be replaced with Option 2's specific presets, not the generic ones
        self.assertEqual(sc_repeated.styles[1].name, "Architectural Daylight")
        self.assertEqual(sc_repeated.styles[2].name, "High-Velocity Kinetic")

    def test_clean_taxonomy_text(self):
        # 1. Strips CJK and Wikipedia parentheticals
        raw = "Tokusatsu (特撮（とくさつ）; lit. 'special filming') is a Japanese term for live-action films."
        cleaned = _clean_taxonomy_text(raw)
        self.assertNotIn("特撮", cleaned)
        self.assertNotIn("とくさつ", cleaned)
        self.assertNotIn("lit.", cleaned)
        self.assertIn("Tokusatsu", cleaned)

        # 2. Strips Cyrillic / Hebrew
        raw_cyr = "Chernukha (хнрачуе) gritty realism"
        cleaned_cyr = _clean_taxonomy_text(raw_cyr)
        self.assertNotIn("хнрачуе", cleaned_cyr)
        self.assertIn("Chernukha", cleaned_cyr)

        # 3. Strips empty quotes
        raw_quotes = "embodying '' in the world"
        cleaned_quotes = _clean_taxonomy_text(raw_quotes)
        self.assertNotIn("''", cleaned_quotes)

    def test_format_timed_omni_prompt_length_and_deduplication(self):
        shots = [
            VideoShot(
                shot_number=i,
                time_range=f"00:0{2 * i - 2} - 00:0{2 * i}",
                action=f"Action step {i} of the protagonist.",
                camera="Slit-scan — A visual effect that distorts images by scanning a narrow vertical or horizontal slit across scenes.",
                lighting_atmosphere="Golden Hour Low-Angle Lens Flare [2800K Honeyed Warmth] — Raking horizontal sunlight striking glass.",
            )
            for i in range(1, 6)
        ]
        style_profile = {
            "genre": {
                "name": "Tokusatsu",
                "description": "Tokusatsu (特撮（とくさつ）; lit. 'special filming') practical effects.",
            },
            "visual_style": {"name": "Retro Future", "description": "Analog aesthetic."},
            "camera_movement": {
                "name": "Slit-scan",
                "description": "A visual effect that distorts images by scanning a narrow vertical or horizontal slit across scenes.",
            },
            "lighting": {
                "name": "Golden Hour",
                "description": "Raking horizontal sunlight striking glass.",
            },
        }

        prompt = format_timed_omni_prompt(shots=shots, genre="Tokusatsu", style_profile=style_profile)

        # Must not contain CJK
        self.assertNotIn("特撮", prompt)
        # Must stay well under 1,500 chars (unlike the original 6,495 chars)
        self.assertLess(len(prompt), 1500)
        # Camera description must not be repeated 5 times across the shots
        self.assertEqual(prompt.count("A visual effect that distorts images"), 1)
        # All 5 shots must be strictly preserved
        for i in range(1, 6):
            self.assertIn(f"Shot {i}", prompt)

    def test_sanitize_i2v_prompt_safety_and_scripts(self):
        raw_prompt = (
            "Cast this exact human person (their facial identity and likeness) as the protagonist in Tokusatsu (特撮（とくさつ）). "
            "Use only the person's face/identity from the reference photo. Shot 1 (00:00 - 00:02): The protagonist moves forward."
        )
        cleaned = sanitize_i2v_prompt(raw_prompt)
        self.assertNotIn("facial identity", cleaned)
        self.assertNotIn("likeness", cleaned)
        self.assertNotIn("person's face", cleaned)
        self.assertNotIn("特撮", cleaned)
        self.assertIn("Shot 1", cleaned)
        self.assertLessEqual(len(cleaned), 1200)

    def test_sanitize_i2v_prompt_preserves_full_five_shot_prompt(self):
        prompt = (
            "Cinematic 9:16 Visionary Solarpunk. Setting grounded in Solarpunk (Futuristic). "
            "Visual style: Organic Architecture. Atmosphere & Optics: Camera: 360 Arc; Lighting: Prismatic Sun. "
            "Shot 1 (00:00 - 00:02): The protagonist steps onto a sunlit glass sky-terrace overlooking a spiral city. "
            "Shot 2 (00:02 - 00:04): The protagonist reaches toward floating geometric prisms rotating in zero gravity. "
            "Shot 3 (00:04 - 00:06): Touch ignites branching spectral light beams through lush vertical garden canopies. "
            "Shot 4 (00:06 - 00:08): The entire bio-architectural canopy pulses with synchronized emerald and gold light. "
            "Shot 5 (00:08 - 00:10): The protagonist turns toward the horizon with a calm visionary smile into final frame. "
            "Ending Anchor: In the final frame, the action resolves into a steady, iconic hero hold. "
            "Photorealistic physical dynamics, zero warping or morphing, natural surface textures, pristine temporal stability."
        )
        cleaned = sanitize_i2v_prompt(prompt)
        for i in range(1, 6):
            self.assertIn(f"Shot {i}", cleaned)
        self.assertIn("00:00 - 00:02", cleaned)
        self.assertIn("00:08 - 00:10", cleaned)

    def test_all_styles_json_entries_produce_clean_omni_prompts(self):
        import json

        styles_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents", "video_editor", "styles.json"
        )
        with open(styles_path, encoding="utf-8") as f:
            data = json.load(f)

        genres = data.get("genres", [])
        visual_styles = data.get("visual_styles", [])
        camera_moves = data.get("camera_movements", [])
        lightings = data.get("lighting", [])

        # Test cross-combinations across the catalog
        for i in range(min(20, len(genres))):
            g = genres[i]
            s = visual_styles[i % len(visual_styles)]
            c = camera_moves[i % len(camera_moves)]
            lighting_item = lightings[i % len(lightings)]
            sp = {
                "genre": g,
                "visual_style": s,
                "camera_movement": c,
                "lighting": lighting_item,
            }
            shots = [
                VideoShot(
                    shot_number=n,
                    time_range=f"00:0{2 * n - 2} - 00:0{2 * n}",
                    action=f"Action step {n} for protagonist.",
                    camera=c.get("name", "Camera move"),
                    lighting_atmosphere=lighting_item.get("name", "Lighting setup"),
                )
                for n in range(1, 6)
            ]
            prompt = format_timed_omni_prompt(shots=shots, genre=g.get("name", ""), style_profile=sp)
            # Must have no CJK or Cyrillic characters
            self.assertFalse(
                re.search(r"[\u3040-\u30ff\u4e00-\u9fff\u0400-\u04ff]", prompt),
                f"Non-Latin script found in prompt for {g['name']}: {prompt}",
            )
            # Must be strictly under 1,500 chars
            self.assertLess(len(prompt), 1500, f"Prompt too long ({len(prompt)}) for {g['name']}")
            # Must not contain safety triggers
            self.assertNotIn("facial identity", prompt.lower())
            self.assertNotIn("likeness", prompt.lower())
            self.assertNotIn("person's face", prompt.lower())
            # All 5 shots must be strictly preserved
            for n in range(1, 6):
                self.assertIn(f"Shot {n}", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
