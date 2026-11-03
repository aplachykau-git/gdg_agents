"""Event details and social profiles, set in the conversation instead of a Settings page.

The user tells an agent "DevFest is on 10 October, our Instagram is instagram.com/gdgkrakow" (or
fills the card the agent shows), and :func:`update_event_profile` merges that into the session
state keys read by :func:`agents.common.event_profile.event_from_state`. The returned
``event_profile`` UI payload is an editable card; the frontend stores the profile it carries so
that every later session starts with it.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, List, Optional

from agents.common import ui_payloads
from agents.common.event_profile import (
    NETWORKS,
    EventProfile,
    event_from_state,
    normalise_url,
    parse_date,
    parse_hashtags,
)

logger = logging.getLogger(__name__)

FIELDS = (
    "name",
    "date",
    "website",
    "registration_url",
    "venue",
    "highlights",
    "hashtags",
    "social_profiles",
    "countdown",
)
REQUIRED_FOR = {"countdown": ("date",)}


def profile_dict(event: EventProfile) -> dict:
    return {
        "name": event.name,
        "date": event.date.isoformat() if event.date else "",
        "website": event.website,
        "registration_url": event.registration_url,
        "venue": event.venue,
        "highlights": event.highlights,
        "hashtags": list(event.hashtags),
        # No profiles saved yet: start from the networks posts currently go to (LinkedIn + Instagram).
        "social_profiles": [{"network": p.network, "url": p.url, "post": p.post} for p in event.profiles]
        or [{"network": c, "url": "", "post": True} for c in event.channels],
        "countdown": event.countdown,
    }


def state_keys(profile: dict) -> dict:
    """Session state keys (the same ones the frontend sends) for a profile dict."""
    profiles = profile.get("social_profiles") or []
    return {
        "event_name": profile.get("name", ""),
        "event_date": profile.get("date", ""),
        "event_website": profile.get("website", ""),
        "event_registration_url": profile.get("registration_url", ""),
        "event_venue": profile.get("venue", ""),
        "event_highlights": profile.get("highlights", ""),
        "event_hashtags": " ".join(profile.get("hashtags") or []),
        "social_profiles": profiles,
        "social_channels": [
            p["network"] for p in profiles if p.get("post") and NETWORKS.get(p["network"], {}).get("plannable")
        ],
        "countdown_plan": profile.get("countdown", ""),
    }


def _merge_profiles(current: list[dict], updates: list[dict]) -> list[dict]:
    merged = {p["network"]: dict(p) for p in current}
    order = [p["network"] for p in current]
    for raw in updates or []:
        if not isinstance(raw, dict):
            continue
        network = str(raw.get("network") or "").strip().lower()
        network = "x" if network == "twitter" else network
        if network not in NETWORKS:
            continue
        if raw.get("remove"):
            merged.pop(network, None)
            order = [n for n in order if n != network]
            continue
        entry = merged.get(network, {"network": network, "url": "", "post": bool(NETWORKS[network]["plannable"])})
        if raw.get("url"):
            entry["url"] = normalise_url(str(raw["url"]))
        if "post" in raw:
            entry["post"] = bool(raw["post"]) and bool(NETWORKS[network]["plannable"])
        merged[network] = entry
        if network not in order:
            order.append(network)
    return [merged[n] for n in order if n in merged]


def update_event_profile(
    name: str = "",
    date: str = "",
    website: str = "",
    registration_url: str = "",
    venue: str = "",
    highlights: str = "",
    hashtags: str = "",
    social_profiles: Optional[List[dict]] = None,
    countdown: str = "",
    clear: Optional[List[str]] = None,
    ask: Optional[List[str]] = None,
    tool_context: Optional[Any] = None,
) -> dict:
    """Save the event details and social profiles the user gave in the conversation, or show
    them as an editable card.

    Call it with ONLY the fields the user stated in this conversation; values not passed are
    kept. Call it without arguments to show the current details when the user wants to see or
    change them. The card lets the user edit and save everything; it is remembered for future
    chats.

    Args:
        name: Event name, e.g. "DevFest Kraków 2027".
        date: Event day as "YYYY-MM-DD".
        website: Event website; posts always link here.
        registration_url: Registration page, if different from the website.
        venue: Venue name and address.
        highlights: Facts posts may use, e.g. "2 stages, 15+ speakers, 4 workshops".
        hashtags: Space-separated hashtags; the first one goes into every post.
        social_profiles: Our profiles, e.g. [{"network": "instagram", "url": "https://instagram.com/gdgkrakow",
            "post": true}]. Networks: linkedin, instagram, facebook, x, threads, bluesky, mastodon (can get
            posts), youtube, tiktok, discord, telegram, gdg (links only). Use {"network": "x", "remove": true}
            to remove one. "post": false keeps the link but plans no posts there.
        countdown: Countdown sequence, one "days: theme" per line, only if the user gives one.
        clear: Field names to empty, e.g. ["registration_url"].
        ask: Field names the user still has to fill in (e.g. ["date"]); the card highlights them.
    """
    state = getattr(tool_context, "state", None)
    current = profile_dict(event_from_state(state if state is not None else {}))
    updated = dict(current)
    changed: list[str] = []
    errors: list[str] = []

    def set_field(key: str, value: Any) -> None:
        if value != current.get(key):
            updated[key] = value
            changed.append(key)

    if name.strip():
        set_field("name", name.strip())
    if date.strip():
        parsed = parse_date(date)
        if parsed is None:
            errors.append(f"Could not read the date '{date}'; use YYYY-MM-DD.")
        else:
            set_field("date", parsed.isoformat())
    for key, value in (("website", website), ("registration_url", registration_url)):
        if value.strip():
            set_field(key, normalise_url(value))
    for key, value in (("venue", venue), ("highlights", highlights), ("countdown", countdown)):
        if value.strip():
            set_field(key, value.strip())
    if hashtags.strip():
        set_field("hashtags", list(parse_hashtags(hashtags)))
    if social_profiles:
        set_field("social_profiles", _merge_profiles(current["social_profiles"], social_profiles))
    for key in clear or []:
        if key in FIELDS and key not in ("name", "website"):
            set_field(key, [] if key in ("hashtags", "social_profiles") else "")

    if changed and state is not None:
        try:
            for key, value in state_keys(updated).items():
                state[key] = value
        except Exception:
            logger.debug("Could not write the event profile to the session state", exc_info=True)

    missing = [f for f in (ask or []) if f in FIELDS]
    if not updated["date"] and "date" not in missing and ask is not None:
        missing.append("date")
    # Re-read so the payload shows exactly what agents will see (defaults, normalised profiles).
    shown = profile_dict(event_from_state(state_keys(updated))) if changed else updated
    return {
        "status": "error" if errors and not changed else "success",
        "changed": changed,
        "errors": errors,
        "missing": missing,
        "profile": shown,
        "message": (
            "Saved: " + ", ".join(changed) + ". The card shows the event details."
            if changed
            else "The card shows the event details; the user can edit and save them."
        ),
        "ui": ui_payloads.event_profile(
            shown,
            missing=missing,
            persist=bool(changed),
            updated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        ),
    }
