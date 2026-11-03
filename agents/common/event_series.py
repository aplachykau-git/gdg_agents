"""Event series (Build with AI / DevFest) chosen in the studio settings.

The frontend sends the choice as `video_template` in the session state on every message; the
same switch picks the speaker-card video template, the LinkedIn wording and the agenda intro.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

DEFAULT_SERIES = "build_with_ai"
DEFAULT_CITY = "Krakow"

# Placeholders baked into agent instruction templates and filled per message from the settings.
CITY_TOKEN = "__COMMUNITY_CITY__"  # "Krakow"
COMMUNITY_TOKEN = "__COMMUNITY_NAME__"  # "GDG Krakow"
CITY_TAG_TOKEN = "__COMMUNITY_CITY_TAG__"  # "Krakow" as used in the #GDGKrakow hashtag


@dataclass(frozen=True)
class EventSeries:
    id: str
    name: str
    hashtag: str
    agenda_intro: str  # first sentence of the agenda; "{city}" is replaced with the community name
    post_context: str  # how posts should frame the event


EVENT_SERIES: dict[str, EventSeries] = {
    "build_with_ai": EventSeries(
        id="build_with_ai",
        name="Build with AI",
        hashtag="#BuildWithAI",
        agenda_intro=(
            "Build with AI is a community-led event series in {city} where people of all backgrounds "
            "come together to explore and build with AI."
        ),
        post_context=(
            "The talk is part of Build with AI, a community-led event series about exploring and building with AI."
        ),
    ),
    "devfest": EventSeries(
        id="devfest",
        name="DevFest",
        hashtag="#DevFest",
        agenda_intro=(
            "DevFest {city} is part of DevFest, the global series of community-run developer events organised "
            "by Google Developer Groups, bringing developers together to learn, share and build."
        ),
        post_context=(
            "The talk is part of DevFest, the global series of community-run developer events organised by "
            "Google Developer Groups."
        ),
    ),
}


def series_from_state(state: Any) -> EventSeries:
    """Series selected in the settings (`video_template` / `videoTemplate`), Build with AI by default."""
    value = None
    for key in ("video_template", "videoTemplate"):
        try:
            value = state.get(key)
        except Exception:
            value = None
        if value:
            break
    key = str(value or DEFAULT_SERIES).strip().lower().replace("-", "_")
    return EVENT_SERIES.get(key, EVENT_SERIES[DEFAULT_SERIES])


def _strip_gdg(name: str) -> str:
    name = (name or "").strip()
    if name.upper().startswith("GDG "):
        name = name[4:].strip()
    return name


def default_city() -> str:
    """City when the settings do not provide one: COMMUNITY_NAME / GDG_COMMUNITY_NAME env, else Krakow."""
    for key in ("COMMUNITY_NAME", "GDG_COMMUNITY_NAME"):
        city = _strip_gdg(os.getenv(key, ""))
        if city and city.lower() not in {"community", "your community name"}:
            return city
    return DEFAULT_CITY


def city_from_state(state: Any, fallback: str | None = None) -> str:
    """Community city for texts: "GDG Krakow" from the settings becomes "Krakow"."""
    try:
        name = str(state.get("community_name") or state.get("communityName") or "")
    except Exception:
        name = ""
    return _strip_gdg(name) or fallback or default_city()


def city_hashtag(city: str) -> str:
    """ "New York" -> "NewYork" so that #GDG{tag} stays one hashtag."""
    return re.sub(r"[^\w]", "", city, flags=re.UNICODE) or DEFAULT_CITY


def fill_city(template: str, city: str) -> str:
    """Replace the city placeholders of an instruction template."""
    return (
        template.replace(CITY_TAG_TOKEN, city_hashtag(city))
        .replace(COMMUNITY_TOKEN, f"GDG {city}")
        .replace(CITY_TOKEN, city)
    )
