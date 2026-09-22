import unittest

from agents.video_editor.style_sampler import (
    filter_by_culture,
    filter_by_format,
    load_styles_db,
    pick_random_cinematic_styles,
    search_styles_database,
    styles_to_genre_briefs,
)


class TestStyleSampler(unittest.TestCase):
    def setUp(self):
        load_styles_db.cache_clear()

    def test_load_styles_db(self):
        db = load_styles_db()
        self.assertIsInstance(db, dict)
        self.assertIn("genres", db)
        self.assertIn("visual_styles", db)
        self.assertIn("camera_movements", db)
        self.assertIn("lighting", db)
        self.assertIn("optics_and_color", db)

        # Confirm taxonomy richness from Jenres (590 verified items)
        self.assertGreaterEqual(len(db["genres"]), 100)
        self.assertGreaterEqual(len(db["visual_styles"]), 200)
        self.assertGreaterEqual(len(db["camera_movements"]), 100)
        self.assertGreaterEqual(len(db["lighting"]), 10)
        self.assertGreaterEqual(len(db["optics_and_color"]), 10)

    def test_pick_random_cinematic_styles_returns_distinct_profiles(self):
        styles = pick_random_cinematic_styles(n=5)
        self.assertEqual(len(styles), 5)

        genre_names = [s["genre"]["name"] for s in styles]
        style_names = [s["visual_style"]["name"] for s in styles]

        # No duplicate genres or primary visual styles among the 5
        self.assertEqual(len(set(genre_names)), 5, "Genres should be distinct across all 5 cards")
        self.assertEqual(len(set(style_names)), 5, "Visual styles should be distinct across all 5 cards")

        for s in styles:
            self.assertTrue(s["genre"]["name"])
            self.assertTrue(s["genre"]["description"])
            self.assertTrue(s["visual_style"]["name"])
            self.assertTrue(s["visual_style"]["description"])
            self.assertTrue(s["camera_movement"]["name"])
            self.assertTrue(s["camera_movement"]["description"])
            self.assertTrue(s["lighting"]["name"])
            self.assertTrue(s["lighting"]["description"])
            self.assertTrue(s["prompt_clause"])

            # Prompt clause should embed genre, visual style, and camera
            self.assertIn(s["genre"]["name"], s["prompt_clause"])
            self.assertIn(s["visual_style"]["name"], s["prompt_clause"])

    def test_pick_random_cinematic_styles_with_creative_guidance(self):
        # When guidance is provided, matching categories are prioritized
        styles = pick_random_cinematic_styles(n=5, creative_guidance="cyberpunk noir")
        self.assertEqual(len(styles), 5)

        first_genres = [s["genre"]["name"].lower() for s in styles]
        first_styles = [s["visual_style"]["name"].lower() for s in styles]
        combined = " ".join(first_genres + first_styles)

        # Check that either noir or cyberpunk is reflected in the top picks
        has_match = "noir" in combined or "cyberpunk" in combined or "cyber" in combined
        self.assertTrue(has_match, f"Expected guidance keyword in sampled styles: {combined}")

    def test_filter_by_format_and_culture(self):
        db = load_styles_db()
        genres = db.get("genres", [])

        commercial_genres = filter_by_format(genres, "commercial")
        self.assertTrue(all(g.get("format") == "commercial" for g in commercial_genres))

        french_genres = filter_by_culture(genres, "french")
        self.assertTrue(
            any(
                "france" in g.get("culture_era", "").lower() or "french" in g.get("name", "").lower()
                for g in french_genres
            )
        )

    def test_search_styles_database(self):
        db = load_styles_db()
        results = search_styles_database(db, "anamorphic")
        self.assertGreater(len(results), 0)
        found_lens = any("anamorphic" in item.get("name", "").lower() for _, item in results)
        self.assertTrue(found_lens)

    def test_styles_to_genre_briefs(self):
        styles = pick_random_cinematic_styles(n=5)
        briefs = styles_to_genre_briefs(
            styles=styles,
            talk_title="Agentic Reasoning at Scale",
            speaker_name="Elena Rostova",
            position_company="AI Lead, TechCorp",
            speaker_bio="Expert in autonomous LLM agents.",
        )
        self.assertEqual(len(briefs), 5)

        for b in briefs:
            self.assertTrue(b.id)
            self.assertTrue(b.title)
            self.assertTrue(b.genre)
            self.assertTrue(b.visual_universe)
            self.assertTrue(b.aesthetic_manifesto)
            self.assertTrue(b.narrative_metaphor)
            self.assertIsNotNone(b.style_profile)
            self.assertIn("genre", b.style_profile)
            self.assertIn("visual_style", b.style_profile)
            self.assertIn("prompt_clause", b.style_profile)

            # Check that personal name was not hardcoded into metaphor
            self.assertNotIn("Elena Rostova", b.narrative_metaphor)
            self.assertIn("The protagonist", b.narrative_metaphor)


if __name__ == "__main__":
    unittest.main()
