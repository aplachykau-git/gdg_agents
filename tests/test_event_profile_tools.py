"""Event details set in the conversation: merging, session state and the editable card."""

import unittest
from types import SimpleNamespace

from agents.common.event_profile import event_from_state
from agents.common.event_profile_tools import state_keys, update_event_profile
from agents.linkedin_post_generator import tools


def ctx(**state):
    return SimpleNamespace(state=dict(state))


class UpdateEventProfileTests(unittest.TestCase):
    def test_saves_only_given_fields_into_state(self):
        c = ctx(event_website="https://devfestkrakow.pl/", event_venue="Klaster Zabłocie 20.22")
        result = update_event_profile(date="10.10.2027", highlights="2 stages, 4 workshops", tool_context=c)
        self.assertEqual(result["status"], "success")
        self.assertEqual(sorted(result["changed"]), ["date", "highlights"])
        self.assertEqual(c.state["event_date"], "2027-10-10")
        self.assertEqual(c.state["event_venue"], "Klaster Zabłocie 20.22")  # kept
        ui = result["ui"]
        self.assertEqual(ui["type"], "event_profile")
        self.assertTrue(ui["persist"])
        self.assertTrue(ui["updated_at"])
        self.assertEqual(event_from_state(c.state).date.isoformat(), "2027-10-10")

    def test_social_profiles_merge_and_default_networks(self):
        c = ctx()
        update_event_profile(
            social_profiles=[{"network": "instagram", "url": "instagram.com/gdgkrakow"}], tool_context=c
        )
        nets = {p["network"]: p for p in c.state["social_profiles"]}
        self.assertEqual(set(nets), {"linkedin", "instagram"})  # LinkedIn kept from the defaults
        self.assertEqual(nets["instagram"]["url"], "https://instagram.com/gdgkrakow")
        self.assertEqual(c.state["social_channels"], ["linkedin", "instagram"])

        update_event_profile(
            social_profiles=[
                {"network": "twitter", "url": "https://x.com/gdgkrakow", "post": False},
                {"network": "youtube", "url": "https://youtube.com/@GDGKrakow", "post": True},
                {"network": "linkedin", "remove": True},
            ],
            tool_context=c,
        )
        nets = {p["network"]: p for p in c.state["social_profiles"]}
        self.assertEqual(list(nets), ["instagram", "x", "youtube"])
        self.assertFalse(nets["x"]["post"])
        self.assertFalse(nets["youtube"]["post"])  # links only
        self.assertEqual(c.state["social_channels"], ["instagram"])

    def test_show_without_changes_and_ask(self):
        c = ctx()
        shown = update_event_profile(tool_context=c)
        self.assertEqual(shown["changed"], [])
        self.assertFalse(shown["ui"]["persist"])
        self.assertEqual(c.state, {})
        asked = update_event_profile(ask=["date", "nonsense"], tool_context=c)
        self.assertEqual(asked["missing"], ["date"])

    def test_bad_date_and_clear(self):
        c = ctx(event_registration_url="https://gdg.community.dev/e/1")
        bad = update_event_profile(date="someday", tool_context=c)
        self.assertEqual(bad["status"], "error")
        self.assertTrue(bad["errors"])
        cleared = update_event_profile(clear=["registration_url", "website"], tool_context=c)
        self.assertEqual(cleared["changed"], ["registration_url"])
        self.assertEqual(c.state["event_registration_url"], "")

    def test_state_keys_round_trip(self):
        profile = {
            "name": "DevFest Kraków 2027",
            "date": "2027-10-09",
            "website": "https://devfestkrakow.pl/",
            "hashtags": ["#DevFestKrakow", "#GDGKrakow"],
            "social_profiles": [{"network": "x", "url": "https://x.com/a", "post": True}],
        }
        event = event_from_state(state_keys(profile))
        self.assertEqual(event.name, "DevFest Kraków 2027")
        self.assertEqual(event.channels, ("x",))
        self.assertEqual(event.hashtags, ("#DevFestKrakow", "#GDGKrakow"))

    def test_planner_uses_saved_profile_in_the_same_session(self):
        c = ctx()
        self.assertEqual(tools.plan_countdown_posts(tool_context=c)["error"], "MISSING_EVENT_DATE")
        update_event_profile(date="2099-10-09", tool_context=c)
        self.assertEqual(tools.plan_countdown_posts(tool_context=c)["status"], "success")


if __name__ == "__main__":
    unittest.main()
