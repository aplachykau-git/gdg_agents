"""Tools of the social planner: countdown schedule and the post plan card."""

from __future__ import annotations

import copy
import datetime as dt
import logging
from dataclasses import replace
from typing import Any, List, Optional

from agents.common import ui_payloads
from agents.common.event_profile import event_from_state, parse_channels, parse_date

from .countdown import build_schedule, parse_sequence, validate_posts

logger = logging.getLogger(__name__)

STATE_KEY = "post_plan_schedule"


def _state(tool_context: Any) -> Any:
    return getattr(tool_context, "state", None) or {}


def _today() -> dt.date:
    return dt.date.today()


def plan_countdown_posts(
    event_date: str = "",
    start_date: str = "",
    channels: str = "",
    countdown: str = "",
    tool_context: Optional[Any] = None,
) -> dict:
    """Build the countdown posting schedule for the saved event (see update_event_profile).

    Returns dated slots ("14 days to go: Hands-on workshops") with the networks chosen for each
    slot, the format (LinkedIn text post, Instagram feed post / carousel / reel / story), the reason
    for the choice, and the platform rules. Write one post per slot and network, then call
    `publish_post_plan`.

    Args:
        event_date: "YYYY-MM-DD" only if the user names a date; empty = the saved event date.
        start_date: "YYYY-MM-DD" to plan from a later day than today; empty = today.
        channels: Comma-separated networks only if the user asks for specific ones, from
            linkedin, instagram, facebook, x, threads, bluesky, mastodon; empty = the networks
            enabled for posts in the event profile.
        countdown: Custom sequence only if the user gives one, one "days: theme" per line
            (e.g. "14: Hands-on workshops"); empty = the saved sequence or the default.
    """
    event = event_from_state(_state(tool_context))
    if event_date:
        parsed = parse_date(event_date)
        if parsed is None:
            return {"status": "error", "message": f"Could not read the event date '{event_date}', use YYYY-MM-DD."}
        event = replace(event, date=parsed)
    if channels:
        event = replace(event, channels=parse_channels(channels))
    if countdown:
        event = replace(event, countdown=countdown)
    if event.date is None:
        return {
            "status": "error",
            "error": "MISSING_EVENT_DATE",
            "message": 'The event date is not set. Call update_event_profile(ask=["date"]) so the user can fill it in.',
        }
    today = parse_date(start_date) or _today()
    try:
        schedule = build_schedule(event, today, parse_sequence(event.countdown))
    except ValueError as exc:
        return {"status": "error", "error": "NO_NETWORKS", "message": str(exc)}
    if not schedule["slots"]:
        return {
            "status": "error",
            "error": "NOTHING_TO_PLAN",
            "message": f"All countdown milestones for {event.date.isoformat()} are already in the past.",
            "skipped": schedule["skipped"],
        }
    try:
        tool_context.state[STATE_KEY] = schedule
    except Exception:
        logger.debug("No writable tool_context state; schedule is not cached")
    return {"status": "success", **schedule}


def publish_post_plan(posts: List[dict], tool_context: Optional[Any] = None) -> dict:
    """Show the written countdown posts to the user as a plan card (copy, CSV for Sheets, calendar).

    Args:
        posts: One dict per slot and network from `plan_countdown_posts`:
            {"slot_id": "d14", "platform": "linkedin" | "instagram", "text": full post text with
            hashtags at the end, "visual": one-line visual idea}. Links on Instagram are replaced
            with "Link in bio"; the website link and the main event hashtag are added if missing.
    """
    schedule = None
    try:
        schedule = _state(tool_context).get(STATE_KEY)
    except Exception:
        schedule = None
    if not schedule:
        return {
            "status": "error",
            "message": "Call plan_countdown_posts first: there is no schedule in this session.",
        }
    plan = validate_posts(copy.deepcopy(schedule), posts)
    warnings = sum(len(p["warnings"]) for s in plan["slots"] for p in s["posts"].values())
    return {
        "status": "success",
        "posts": sum(plan["counts"].values()),
        "missing": plan["missing"],
        "unknown_slots": plan["unknown"],
        "warnings": warnings,
        "message": "The countdown plan card is shown to the user."
        + (f" Missing posts: {', '.join(plan['missing'])}." if plan["missing"] else ""),
        "ui": ui_payloads.post_plan(plan),
    }
