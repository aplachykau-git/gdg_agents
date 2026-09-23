"""Structured presentation of recommended meetup dates (validated server-side)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel

from agents.common import ui_payloads

BLOCKED_WEEKDAYS = {4: "Friday", 5: "Saturday", 6: "Sunday"}


class MeetupDateOption(BaseModel):
    date: str
    reason: str = ""


def _as_option(raw: Any) -> MeetupDateOption:
    if isinstance(raw, MeetupDateOption):
        return raw
    if isinstance(raw, dict):
        return MeetupDateOption.model_validate(raw)
    return MeetupDateOption(date=str(raw))


def present_meetup_dates(options: list[MeetupDateOption], event_title: str = "", location: str = "") -> dict:
    """Show the recommended meetup dates as interactive calendar cards (Google Calendar / .ics).

    Call this with your final recommendation (best option first), then give the short reasoning
    in text. Dates are validated: weekends, Fridays and past dates are rejected.

    Args:
        options: 1-3 options, best first. Each has `date` (YYYY-MM-DD) and a one-sentence `reason`.
        event_title: Optional event name, e.g. "Build with AI Krakow".
        location: Optional venue, only if the user mentioned it.
    """
    today = dt.date.today()
    dates, problems = [], []
    for raw in options or []:
        option = _as_option(raw)
        try:
            day = dt.date.fromisoformat(option.date.strip())
        except ValueError:
            problems.append(f"'{option.date}' is not a YYYY-MM-DD date")
            continue
        if day < today:
            problems.append(f"{day.isoformat()} is in the past")
        elif day.weekday() in BLOCKED_WEEKDAYS:
            problems.append(f"{day.isoformat()} is a {BLOCKED_WEEKDAYS[day.weekday()]}")
        else:
            dates.append(
                {
                    "date": day.isoformat(),
                    "weekday": day.strftime("%A"),
                    "reason": option.reason.strip(),
                    "primary": not dates,
                }
            )
    if problems or not dates:
        return {
            "status": "error",
            "message": "Please choose other dates: " + ("; ".join(problems) or "no dates given") + ".",
        }
    return {
        "status": "ok",
        "message": f"{len(dates)} date option(s) are shown to the user as calendar cards.",
        "ui": ui_payloads.meetup_dates(dates, event_title=event_title.strip(), location=location.strip()),
    }
