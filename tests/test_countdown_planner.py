"""Countdown post planner: schedule, network choice, post validation, tools and settings."""

import datetime as dt
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from agents.common.event_profile import (
    DEFAULT_WEBSITE,
    event_from_state,
    normalise_url,
    parse_channels,
    parse_hashtags,
)
from agents.linkedin_post_generator import tools
from agents.linkedin_post_generator.countdown import (
    DEFAULT_SEQUENCE,
    LINKEDIN_PER_WEEK,
    build_schedule,
    parse_sequence,
    plan_csv,
    sequence_text,
    validate_posts,
)

ROOT = Path(__file__).resolve().parents[1]
EVENT_STATE = {
    "event_name": "DevFest Kraków",
    "event_date": "2027-10-09",
    "event_website": "devfestkrakow.pl",
    "event_hashtags": "#DevFestKrakow #DevFest #GDGKrakow",
}


def platforms(slot):
    return [c["platform"] for c in slot["channels"]]


class EventProfileTests(unittest.TestCase):
    def test_defaults(self):
        event = event_from_state({})
        self.assertEqual(event.website, DEFAULT_WEBSITE)
        self.assertEqual(event.cta_url, DEFAULT_WEBSITE)
        self.assertIsNone(event.date)
        self.assertEqual(event.channels, ("linkedin", "instagram"))

    def test_name_and_hashtags_follow_the_series(self):
        devfest = event_from_state({"video_template": "devfest", "community_name": "GDG Krakow"})
        self.assertEqual(devfest.name, "DevFest Kraków")
        self.assertEqual(devfest.hashtags[0], "#DevFestKrakow")
        bwai = event_from_state({"video_template": "build_with_ai"})
        self.assertEqual(bwai.name, "Build with AI Kraków")
        self.assertEqual(bwai.hashtags[0], "#BuildWithAI")
        self.assertEqual(bwai.website, DEFAULT_WEBSITE)

    def test_from_settings(self):
        event = event_from_state(
            {**EVENT_STATE, "event_registration_url": "gdg.community.dev/e/1", "social_channels": ["instagram"]}
        )
        self.assertEqual(event.date, dt.date(2027, 10, 9))
        self.assertEqual(event.website, "https://devfestkrakow.pl")
        self.assertEqual(event.cta_url, "https://gdg.community.dev/e/1")
        self.assertEqual(event.channels, ("instagram",))
        self.assertIn("Website (always link this one): https://devfestkrakow.pl", event.as_prompt_block())

    def test_parsers(self):
        self.assertEqual(parse_hashtags("DevFest, #GDG Krakow #devfest"), ("#DevFest", "#GDG", "#Krakow"))
        self.assertEqual(parse_channels("Instagram;LinkedIn"), ("linkedin", "instagram"))
        self.assertEqual(parse_channels("tiktok"), ("linkedin", "instagram"))
        self.assertEqual(normalise_url("devfestkrakow.pl/"), "https://devfestkrakow.pl/")
        self.assertEqual(normalise_url("http://x.pl"), "http://x.pl")


class SequenceTests(unittest.TestCase):
    def test_round_trip_default(self):
        self.assertEqual(parse_sequence(sequence_text()), DEFAULT_SEQUENCE)
        self.assertIn("12: Agenda is live", sequence_text())

    def test_empty_or_garbage_gives_default(self):
        self.assertEqual(parse_sequence(""), DEFAULT_SEQUENCE)
        self.assertEqual(parse_sequence("hello\nworld"), DEFAULT_SEQUENCE)

    def test_custom_lines(self):
        seq = parse_sequence(
            "T-45: Call for volunteers\n- 14 days — Hands-on workshops\n3 | Swag preview\n100: Too early"
        )
        self.assertEqual([m.days for m in seq], [100, 45, 14, 3])
        workshops = next(m for m in seq if m.days == 14)
        self.assertIn("laptop", workshops.angle)  # kept the default angle
        swag = next(m for m in seq if m.days == 3)
        self.assertGreater(swag.instagram, swag.linkedin)  # visual topic leans to Instagram

    def test_frontend_default_matches_backend(self):
        config = (ROOT / "frontend/src/lib/config.js").read_text(encoding="utf-8")
        block = re.search(r"DEFAULT_COUNTDOWN_PLAN = \[(.*?)\]", config, re.DOTALL).group(1)
        lines = re.findall(r"'([^']+)'", block)
        self.assertEqual("\n".join(lines), sequence_text())


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.event = event_from_state(EVENT_STATE)

    def test_dates_and_labels(self):
        schedule = build_schedule(self.event, dt.date(2027, 9, 1))
        first, last = schedule["slots"][0], schedule["slots"][-1]
        self.assertEqual((first["date"], first["label"]), ("2027-09-09", "30 days to go"))
        self.assertEqual((last["date"], last["label"]), ("2027-10-09", "Today"))
        self.assertEqual(schedule["slots"][-2]["label"], "Tomorrow")
        self.assertEqual([s["date"] for s in schedule["slots"]], sorted(s["date"] for s in schedule["slots"]))
        self.assertEqual(schedule["skipped"], [])

    def test_past_milestones_are_skipped(self):
        schedule = build_schedule(self.event, dt.date(2027, 9, 28))
        self.assertEqual([s["days"] for s in schedule["skipped"]], [30, 21, 14, 12])
        self.assertEqual(schedule["slots"][0]["days_left"], 10)

    def test_network_choice_follows_topic(self):
        slots = {s["days_left"]: s for s in build_schedule(self.event, dt.date(2027, 9, 1))["slots"]}
        self.assertEqual(platforms(slots[10]), ["instagram"])  # community spaces: visual
        self.assertEqual(platforms(slots[5]), ["linkedin"])  # mentoring and careers: professional
        self.assertIn("instagram", platforms(slots[1]))
        self.assertEqual(next(c for c in slots[1]["channels"] if c["platform"] == "instagram")["format"], "story")
        self.assertEqual(next(c for c in slots[21]["channels"] if c["platform"] == "instagram")["format"], "carousel")
        for slot in slots.values():
            for channel in slot["channels"]:
                self.assertTrue(channel["reason"])

    def test_linkedin_cadence(self):
        schedule = build_schedule(self.event, dt.date(2027, 9, 1))
        dates = [dt.date.fromisoformat(s["date"]) for s in schedule["slots"] if "linkedin" in platforms(s)]
        for start in dates:
            window = [d for d in dates if start <= d < start + dt.timedelta(days=7)]
            self.assertLessEqual(len(window), LINKEDIN_PER_WEEK)
        # The dropped LinkedIn slot keeps an Instagram post.
        self.assertTrue(all(s["channels"] for s in schedule["slots"]))

    def test_only_selected_networks(self):
        event = event_from_state({**EVENT_STATE, "social_channels": ["linkedin"]})
        schedule = build_schedule(event, dt.date(2027, 9, 1))
        self.assertTrue(all(platforms(s) == ["linkedin"] for s in schedule["slots"]))
        self.assertEqual(set(schedule["rules"]), {"linkedin"})

    def test_missing_date(self):
        with self.assertRaises(ValueError):
            build_schedule(event_from_state({}), dt.date(2027, 9, 1))


class ValidatePostsTests(unittest.TestCase):
    def setUp(self):
        self.schedule = build_schedule(event_from_state(EVENT_STATE), dt.date(2027, 9, 1))

    def post(self, platform, text, slot_id="d30", **extra):
        plan = validate_posts(self.schedule, [{"slot_id": slot_id, "platform": platform, "text": text, **extra}])
        return plan, next(s for s in plan["slots"] if s["id"] == slot_id)["posts"][platform]

    def test_linkedin_gets_link_and_primary_hashtag(self):
        _, post = self.post(
            "linkedin", "Save the date: DevFest Kraków is back.\n\nFree, limited places.\n\n#DevFest #AI #Cloud"
        )
        self.assertIn("https://devfestkrakow.pl", post["text"])
        self.assertTrue(post["text"].rstrip().endswith("#DevFestKrakow"))
        self.assertIn("added the website link", post["fixes"])
        self.assertEqual(post["warnings"], [])

    def test_linkedin_keeps_existing_link(self):
        _, post = self.post("linkedin", "See you at https://devfestkrakow.pl/ soon!\n\n#DevFestKrakow #DevFest #AI")
        self.assertEqual(post["text"].count("devfestkrakow.pl"), 1)
        self.assertNotIn("added the website link", post["fixes"])

    def test_instagram_removes_links_and_adds_bio(self):
        _, post = self.post(
            "instagram",
            "30 days to go! Register at https://devfestkrakow.pl now.\n\n#DevFestKrakow #DevFest #GDGKrakow #AI #Krakow",
        )
        self.assertNotIn("http", post["text"])
        self.assertIn("Link in bio.", post["text"])
        self.assertIn("removed links (not clickable in captions)", post["fixes"])

    def test_hashtags_trimmed_but_primary_kept(self):
        tags = " ".join(f"#Tag{i}" for i in range(12))
        _, post = self.post("linkedin", f"Hello https://devfestkrakow.pl\n\n{tags}")
        self.assertEqual(len(post["hashtags"]), 7)
        self.assertEqual(post["hashtags"][-1], "#DevFestKrakow")

    def test_too_few_hashtags_warns(self):
        _, post = self.post("instagram", "Hi! Link in bio.")
        self.assertTrue(any("hashtags" in w for w in post["warnings"]))

    def test_long_first_line_warns(self):
        _, post = self.post("instagram", "x" * 200 + "\n\n#DevFestKrakow #a #b #c #d Link in bio")
        self.assertTrue(any("first line" in w for w in post["warnings"]))

    def test_catches_the_mistakes_from_the_team_sheet(self):
        # Real issues found in the DevFest Kraków 2026 sheet: "25 DAYS" in the 30-day post,
        # a stray "#GDG#" hashtag and an unfilled [REGISTRATION LINK] placeholder.
        _, post = self.post(
            "linkedin",
            "🚀 25 DAYS TO DEVFEST KRAKÓW 2026!\n\nThe countdown starts now 👀\n\n🎟️ [REGISTRATION LINK]\n\n#DevFestKrakow #GDG# #GDGKrakow",
        )
        self.assertTrue(any('"25 days"' in w for w in post["warnings"]))
        self.assertIn("fixed malformed hashtags", post["fixes"])
        self.assertIn("filled link placeholders", post["fixes"])
        self.assertNotIn("[REGISTRATION LINK]", post["text"])
        self.assertNotIn("#GDG#", post["text"])
        self.assertEqual(post["text"].count("devfestkrakow.pl"), 1)

    def test_matching_countdown_number_is_fine(self):
        _, post = self.post(
            "linkedin", "⏰ 30 DAYS TO DEVFEST KRAKÓW!\n\nhttps://devfestkrakow.pl\n\n#DevFestKrakow #GDGKrakow #GDG"
        )
        self.assertEqual(post["warnings"], [])

    def test_missing_and_unknown(self):
        plan = validate_posts(self.schedule, [{"slot_id": "d99", "platform": "linkedin", "text": "x"}])
        self.assertEqual(plan["unknown"], ["d99/linkedin"])
        self.assertIn("d30/linkedin", plan["missing"])
        self.assertEqual(sum(plan["counts"].values()), 0)

    def test_csv(self):
        plan = validate_posts(self.schedule, [{"slot_id": "d30", "platform": "linkedin", "text": 'He said "hi", ok'}])
        csv = plan_csv(plan)
        self.assertTrue(csv.startswith("Date,Weekday,Days left,Theme,Platform"))
        self.assertIn('"He said ""hi"", ok', csv)
        self.assertIn("To write", csv)


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.ctx = SimpleNamespace(state=dict(EVENT_STATE))

    def test_plan_then_publish(self):
        planned = tools.plan_countdown_posts(start_date="2027-09-20", tool_context=self.ctx)
        self.assertEqual(planned["status"], "success")
        self.assertIn(tools.STATE_KEY, self.ctx.state)
        slot = planned["slots"][0]
        posts = [
            {"slot_id": slot["id"], "platform": c["platform"], "text": "Countdown! #DevFest"} for c in slot["channels"]
        ]
        result = tools.publish_post_plan(posts, tool_context=self.ctx)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["ui"]["type"], "post_plan")
        self.assertEqual(result["posts"], len(posts))
        self.assertTrue(result["missing"])

    def test_event_date_override_and_errors(self):
        self.assertEqual(
            tools.plan_countdown_posts(tool_context=SimpleNamespace(state={}))["error"], "MISSING_EVENT_DATE"
        )
        self.assertEqual(tools.plan_countdown_posts(event_date="soon", tool_context=self.ctx)["status"], "error")
        past = tools.plan_countdown_posts(event_date="2020-01-01", tool_context=self.ctx)
        self.assertEqual(past["error"], "NOTHING_TO_PLAN")
        ok = tools.plan_countdown_posts(event_date="2099-05-01", channels="instagram", tool_context=self.ctx)
        self.assertTrue(all(c["platform"] == "instagram" for s in ok["slots"] for c in s["channels"]))

    def test_publish_without_plan(self):
        self.assertEqual(tools.publish_post_plan([], tool_context=SimpleNamespace(state={}))["status"], "error")


class AgentWiringTests(unittest.TestCase):
    def test_agent_has_tools_and_event_block(self):
        from agents.common.event_series import series_from_state
        from agents.linkedin_post_generator.agent import build_instruction, linkedin_agent

        names = [t.__name__ for t in linkedin_agent.tools]
        self.assertEqual(names, ["update_event_profile", "plan_countdown_posts", "publish_post_plan"])
        text = build_instruction(series_from_state({}), "Krakow", event_from_state(EVENT_STATE))
        self.assertIn("https://devfestkrakow.pl", text)
        self.assertIn("plan_countdown_posts", text)
        self.assertIn("#GDGKrakow", text)


if __name__ == "__main__":
    unittest.main()


class SocialProfileTests(unittest.TestCase):
    PROFILES = [
        {"network": "linkedin", "url": "https://www.linkedin.com/company/gdg-krakow/", "post": True},
        {"network": "instagram", "url": "instagram.com/gdgkrakow/", "post": True},
        {"network": "twitter", "url": "https://x.com/gdgkrakow", "post": True},
        {"network": "youtube", "url": "https://www.youtube.com/@GDGKrakow", "post": True},
        {"network": "threads", "url": "", "post": "false"},
        {"network": "myspace", "url": "https://myspace.com/x"},
        {"network": "instagram", "url": "https://instagram.com/duplicate"},
    ]

    def test_parse_and_handles(self):
        from agents.common.event_profile import parse_profiles, profile_handle

        profiles = parse_profiles(self.PROFILES)
        self.assertEqual([p.network for p in profiles], ["linkedin", "instagram", "x", "youtube", "threads"])
        by = {p.network: p for p in profiles}
        self.assertEqual(by["instagram"].url, "https://instagram.com/gdgkrakow/")
        self.assertEqual(by["instagram"].handle, "@gdgkrakow")
        self.assertEqual(by["x"].handle, "@gdgkrakow")
        self.assertEqual(by["youtube"].handle, "@GDGKrakow")
        self.assertEqual(by["linkedin"].handle, "")
        self.assertFalse(by["threads"].post)
        self.assertFalse(by["youtube"].plannable)
        self.assertEqual(profile_handle("mastodon", "https://mastodon.social/@gdgkrakow"), "@gdgkrakow@mastodon.social")
        self.assertEqual(
            profile_handle("bluesky", "https://bsky.app/profile/gdgkrakow.bsky.social"), "@gdgkrakow.bsky.social"
        )
        self.assertIsNone(parse_profiles(None))

    def test_channels_come_from_ticked_plannable_profiles(self):
        event = event_from_state({**EVENT_STATE, "social_profiles": self.PROFILES, "social_channels": ["facebook"]})
        self.assertEqual(event.channels, ("linkedin", "instagram", "x"))  # youtube: links only, threads: unticked
        block = event.as_prompt_block()
        self.assertIn("Instagram: @gdgkrakow https://instagram.com/gdgkrakow/", block)
        self.assertIn("YouTube: @GDGKrakow", block)
        self.assertIn("Networks we post on: LinkedIn, Instagram, X", block)
        self.assertNotIn("Threads", block)  # listed without a URL and not posting

    def test_no_ticked_network(self):
        state = {**EVENT_STATE, "social_profiles": [{"network": "youtube", "url": "https://youtube.com/@x"}]}
        self.assertEqual(event_from_state(state).channels, ())
        result = tools.plan_countdown_posts(tool_context=SimpleNamespace(state=state))
        self.assertEqual(result["error"], "NO_NETWORKS")

    def test_short_text_network_rules(self):
        state = {**EVENT_STATE, "social_profiles": [{"network": "x", "url": "https://x.com/gdgkrakow"}]}
        schedule = build_schedule(event_from_state(state), dt.date(2027, 9, 1))
        self.assertTrue(schedule["slots"])
        self.assertTrue(all(platforms(s) == ["x"] for s in schedule["slots"]))
        self.assertIn("280", schedule["slots"][0]["channels"][0]["format"])
        self.assertEqual(schedule["event"]["profiles"][0]["handle"], "@gdgkrakow")
        plan = validate_posts(
            schedule,
            [{"slot_id": schedule["slots"][0]["id"], "platform": "x", "text": "x" * 300 + " #AI #Cloud #Krakow"}],
        )
        post = plan["slots"][0]["posts"]["x"]
        self.assertIn("devfestkrakow.pl", post["text"])  # links are clickable on X
        self.assertLessEqual(len(post["hashtags"]), 2)
        self.assertIn("#DevFestKrakow", post["hashtags"])
        self.assertTrue(any("280 limit" in w for w in post["warnings"]))
        self.assertEqual(plan["counts"], {"x": 1})
