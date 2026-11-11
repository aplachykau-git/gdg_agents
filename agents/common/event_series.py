"""Event series (Build with AI / DevFest) chosen in the studio settings.

The frontend sends the choice as `video_template` in the session state on every message; the
same switch picks the speaker-card video template, the LinkedIn wording and the agenda intro.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

DEFAULT_SERIES = "build_with_ai"
DEFAULT_CITY = "Krakow"
DEFAULT_CURRENCY = "PLN"

_CITY_CURRENCIES: dict[str, str] = {
    # Poland
    "krakow": "PLN",
    "cracow": "PLN",
    "warsaw": "PLN",
    "warszawa": "PLN",
    "wroclaw": "PLN",
    "poznan": "PLN",
    "gdansk": "PLN",
    "gdynia": "PLN",
    "sopot": "PLN",
    "trojmiasto": "PLN",
    "katowice": "PLN",
    "silesia": "PLN",
    "lodz": "PLN",
    "lublin": "PLN",
    "szczecin": "PLN",
    "bialystok": "PLN",
    "rzeszow": "PLN",
    "bydgoszcz": "PLN",
    "torun": "PLN",
    "kielce": "PLN",
    "olsztyn": "PLN",
    "opole": "PLN",
    "gliwice": "PLN",
    "czestochowa": "PLN",
    "radom": "PLN",
    "poland": "PLN",
    "polska": "PLN",
    # United Kingdom
    "london": "GBP",
    "manchester": "GBP",
    "birmingham": "GBP",
    "edinburgh": "GBP",
    "glasgow": "GBP",
    "bristol": "GBP",
    "leeds": "GBP",
    "liverpool": "GBP",
    "cambridge": "GBP",
    "oxford": "GBP",
    "belfast": "GBP",
    "cardiff": "GBP",
    "newcastle": "GBP",
    "nottingham": "GBP",
    "sheffield": "GBP",
    "uk": "GBP",
    "united kingdom": "GBP",
    "england": "GBP",
    "scotland": "GBP",
    "wales": "GBP",
    # Eurozone
    "berlin": "EUR",
    "munich": "EUR",
    "munchen": "EUR",
    "hamburg": "EUR",
    "frankfurt": "EUR",
    "cologne": "EUR",
    "koln": "EUR",
    "stuttgart": "EUR",
    "dusseldorf": "EUR",
    "paris": "EUR",
    "lyon": "EUR",
    "marseille": "EUR",
    "toulouse": "EUR",
    "amsterdam": "EUR",
    "rotterdam": "EUR",
    "utrecht": "EUR",
    "eindhoven": "EUR",
    "madrid": "EUR",
    "barcelona": "EUR",
    "valencia": "EUR",
    "seville": "EUR",
    "rome": "EUR",
    "roma": "EUR",
    "milan": "EUR",
    "milano": "EUR",
    "turin": "EUR",
    "naples": "EUR",
    "vienna": "EUR",
    "wien": "EUR",
    "dublin": "EUR",
    "helsinki": "EUR",
    "lisbon": "EUR",
    "lisboa": "EUR",
    "porto": "EUR",
    "brussels": "EUR",
    "bruxelles": "EUR",
    "antwerp": "EUR",
    "tallinn": "EUR",
    "riga": "EUR",
    "vilnius": "EUR",
    "bratislava": "EUR",
    "ljubljana": "EUR",
    "athens": "EUR",
    "luxembourg": "EUR",
    "valletta": "EUR",
    "nicosia": "EUR",
    "zagreb": "EUR",
    # Czechia
    "prague": "CZK",
    "praha": "CZK",
    "brno": "CZK",
    "ostrava": "CZK",
    "czechia": "CZK",
    # Switzerland
    "zurich": "CHF",
    "geneva": "CHF",
    "geneve": "CHF",
    "basel": "CHF",
    "bern": "CHF",
    "lausanne": "CHF",
    "switzerland": "CHF",
    # Ukraine
    "kyiv": "UAH",
    "kiev": "UAH",
    "lviv": "UAH",
    "kharkiv": "UAH",
    "odesa": "UAH",
    "odessa": "UAH",
    "dnipro": "UAH",
    "ukraine": "UAH",
    # Nordics & CEE
    "stockholm": "SEK",
    "gothenburg": "SEK",
    "goteborg": "SEK",
    "malmo": "SEK",
    "sweden": "SEK",
    "oslo": "NOK",
    "bergen": "NOK",
    "norway": "NOK",
    "copenhagen": "DKK",
    "kobenhavn": "DKK",
    "aarhus": "DKK",
    "denmark": "DKK",
    "budapest": "HUF",
    "hungary": "HUF",
    "bucharest": "RON",
    "bucuresti": "RON",
    "cluj": "RON",
    "timisoara": "RON",
    "romania": "RON",
    "sofia": "BGN",
    "bulgaria": "BGN",
    # Americas & APAC
    "new york": "USD",
    "nyc": "USD",
    "san francisco": "USD",
    "los angeles": "USD",
    "seattle": "USD",
    "chicago": "USD",
    "austin": "USD",
    "boston": "USD",
    "atlanta": "USD",
    "miami": "USD",
    "denver": "USD",
    "usa": "USD",
    "united states": "USD",
    "toronto": "CAD",
    "vancouver": "CAD",
    "montreal": "CAD",
    "ottawa": "CAD",
    "canada": "CAD",
    "sydney": "AUD",
    "melbourne": "AUD",
    "brisbane": "AUD",
    "australia": "AUD",
    "tokyo": "JPY",
    "osaka": "JPY",
    "kyoto": "JPY",
    "japan": "JPY",
}

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


def _ascii_lower(value: str) -> str:
    text = (value or "").strip().replace("ł", "l").replace("Ł", "L")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def currency_for_city(city: str | None, fallback: str = DEFAULT_CURRENCY) -> str:
    """Return the ISO-4217 currency code for a community city (e.g. Krakow -> PLN, London -> GBP)."""
    cleaned = _ascii_lower(_strip_gdg(city or ""))
    if not cleaned:
        return fallback
    if cleaned in _CITY_CURRENCIES:
        return _CITY_CURRENCIES[cleaned]
    for token, code in _CITY_CURRENCIES.items():
        if re.search(rf"\b{re.escape(token)}\b", cleaned):
            return code
    return fallback


def community_currency_from_state(state: Any, fallback: str = DEFAULT_CURRENCY) -> str:
    """Resolve the current community's currency from session state or environment."""
    for key in ("community_currency", "communityCurrency"):
        try:
            raw = str(state.get(key) or "").strip().upper() if state else ""
        except Exception:
            raw = ""
        if re.fullmatch(r"[A-Z]{3}", raw):
            return raw

    for env_key in ("COMMUNITY_CURRENCY", "LOCAL_CURRENCY"):
        env_val = os.getenv(env_key, "").strip().upper()
        if re.fullmatch(r"[A-Z]{3}", env_val):
            return env_val

    return currency_for_city(city_from_state(state), fallback=fallback)
