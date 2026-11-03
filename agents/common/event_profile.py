"""The event the studio is working on: details saved from the conversation (event profile card).

The frontend sends these keys in the session state with every message; agents read them through
:func:`event_from_state` so the website, date and hashtags are typed once instead of in every
prompt. Environment variables give deployment-wide defaults.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from dataclasses import dataclass, field
from typing import Any

DEFAULT_WEBSITE = "https://devfestkrakow.pl/"
DEFAULT_EVENT_NAME = "DevFest Kraków"
DEFAULT_HASHTAGS = ("#DevFestKrakow", "#GDGKrakow", "#GDG", "#GoogleDevelopersGroup", "#TechCommunity")
DEFAULT_CHANNELS = ("linkedin", "instagram")

# Social networks the community can list in Settings → Social networks. "plannable" networks get
# countdown posts; the others are profile links only (mentioned in posts as "follow us" links).
# Keep in sync with SOCIAL_NETWORKS in frontend/src/lib/config.js.
NETWORKS: dict[str, dict[str, Any]] = {
    "linkedin": {"label": "LinkedIn", "plannable": True, "domains": ("linkedin.com",)},
    "instagram": {"label": "Instagram", "plannable": True, "domains": ("instagram.com",)},
    "facebook": {"label": "Facebook", "plannable": True, "domains": ("facebook.com", "fb.com")},
    "x": {"label": "X", "plannable": True, "domains": ("x.com", "twitter.com")},
    "threads": {"label": "Threads", "plannable": True, "domains": ("threads.net", "threads.com")},
    "bluesky": {"label": "Bluesky", "plannable": True, "domains": ("bsky.app",)},
    "mastodon": {"label": "Mastodon", "plannable": True, "domains": ()},
    "youtube": {"label": "YouTube", "plannable": False, "domains": ("youtube.com", "youtu.be")},
    "tiktok": {"label": "TikTok", "plannable": False, "domains": ("tiktok.com",)},
    "discord": {"label": "Discord", "plannable": False, "domains": ("discord.gg", "discord.com")},
    "telegram": {"label": "Telegram", "plannable": False, "domains": ("t.me", "telegram.me")},
    "gdg": {"label": "GDG community page", "plannable": False, "domains": ("gdg.community.dev",)},
}
KNOWN_CHANNELS = tuple(n for n, meta in NETWORKS.items() if meta["plannable"])
_HANDLE_NETWORKS = {"instagram", "x", "threads", "tiktok", "youtube", "bluesky", "telegram"}


@dataclass(frozen=True)
class SocialProfile:
    network: str
    url: str = ""
    post: bool = True  # plan countdown posts here (only for plannable networks)

    @property
    def label(self) -> str:
        return NETWORKS.get(self.network, {}).get("label", self.network.title())

    @property
    def plannable(self) -> bool:
        return bool(NETWORKS.get(self.network, {}).get("plannable"))

    @property
    def handle(self) -> str:
        """ "@gdgkrakow" from https://instagram.com/gdgkrakow/, "" when the network has no handles."""
        return profile_handle(self.network, self.url)


def profile_handle(network: str, url: str) -> str:
    if network == "mastodon":
        match = re.match(r"^https?://([^/]+)/@([\w.]+)", url or "")
        return f"@{match.group(2)}@{match.group(1)}" if match else ""
    if network not in _HANDLE_NETWORKS or not url:
        return ""
    path = re.sub(r"^https?://[^/]+/?", "", url.strip()).split("?")[0].strip("/")
    if network == "bluesky":
        path = path.removeprefix("profile/")
    segment = path.split("/")[0] if path else ""
    if not segment or segment in {"channel", "c", "user", "share", "p"}:
        return ""
    return segment if segment.startswith("@") else f"@{segment}"


def parse_profiles(value: Any) -> tuple[SocialProfile, ...] | None:
    """Saved social profiles: [{"network": "instagram", "url": "...", "post": true}, ...].

    Returns None when the setting is absent (older frontends), so the caller can fall back.
    Unknown networks and duplicates are dropped; a network without a URL is still allowed.
    """
    if value in (None, ""):
        return None
    if not isinstance(value, (list, tuple)):
        return None
    out: list[SocialProfile] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        network = str(item.get("network") or "").strip().lower()
        if network == "twitter":
            network = "x"
        if network not in NETWORKS or network in seen:
            continue
        seen.add(network)
        post = item.get("post", True)
        post = str(post).strip().lower() not in {"false", "0", "no", "off"} if isinstance(post, str) else bool(post)
        out.append(SocialProfile(network=network, url=normalise_url(str(item.get("url") or "")), post=post))
    return tuple(out)


@dataclass(frozen=True)
class EventProfile:
    name: str = DEFAULT_EVENT_NAME
    date: dt.date | None = None
    website: str = DEFAULT_WEBSITE
    registration_url: str = ""
    venue: str = ""
    highlights: str = ""
    hashtags: tuple[str, ...] = DEFAULT_HASHTAGS
    channels: tuple[str, ...] = DEFAULT_CHANNELS
    profiles: tuple[SocialProfile, ...] = ()
    countdown: str = ""  # raw "days: theme" lines; empty = default sequence
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def cta_url(self) -> str:
        """Where posts send people: the registration page if set, else the website."""
        return self.registration_url or self.website

    def as_prompt_block(self) -> str:
        lines = [f"- Event: {self.name}"]
        if self.date:
            lines.append(f"- Date: {self.date.strftime('%A, %d %B %Y')}")
        if self.venue:
            lines.append(f"- Venue: {self.venue}")
        lines.append(f"- Website (always link this one): {self.website}")
        if self.registration_url and self.registration_url != self.website:
            lines.append(f"- Registration: {self.registration_url}")
        if self.highlights:
            lines.append(f"- Highlights to draw from: {self.highlights}")
        lines.append(f"- Event hashtags: {' '.join(self.hashtags)}")
        listed = [p for p in self.profiles if p.url]
        if listed:
            lines.append("- Our social profiles (use only these when inviting people to follow us):")
            for p in listed:
                handle = f" {p.handle}" if p.handle else ""
                lines.append(f"  - {p.label}:{handle} {p.url}")
        if self.channels:
            labels = ", ".join(NETWORKS[c]["label"] for c in self.channels)
            lines.append(f"- Networks we post on: {labels}")
        return "\n".join(lines)

    def profile(self, network: str) -> SocialProfile | None:
        return next((p for p in self.profiles if p.network == network), None)


def _get(state: Any, *keys: str) -> Any:
    for key in keys:
        try:
            value = state.get(key)
        except Exception:
            value = None
        if value not in (None, ""):
            return value
    return None


def parse_date(value: Any) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def normalise_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = "https://" + value.lstrip("/")
    return value


def parse_hashtags(value: Any) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        raw = " ".join(str(v) for v in value)
    else:
        raw = str(value or "")
    tags = []
    for token in re.split(r"[\s,;]+", raw):
        token = token.strip()
        if not token:
            continue
        tag = "#" + re.sub(r"[^\w]", "", token.lstrip("#"), flags=re.UNICODE)
        if len(tag) > 1 and tag.lower() not in {t.lower() for t in tags}:
            tags.append(tag)
    return tuple(tags)


def parse_channels(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        items = re.split(r"[\s,;]+", value)
    elif isinstance(value, (list, tuple)):
        items = [str(v) for v in value]
    else:
        return DEFAULT_CHANNELS
    channels = tuple(c for c in KNOWN_CHANNELS if c in {i.strip().lower() for i in items})
    return channels or DEFAULT_CHANNELS


_CITY_DISPLAY = {"krakow": "Kraków", "cracow": "Kraków", "warszawa": "Warszawa", "lodz": "Łódź"}


def default_name_and_tags(series: Any = None, city: str = "") -> tuple[str, tuple[str, ...]]:
    """Event name and hashtags when none are saved: follow the chosen event series."""
    from agents.common.event_series import DEFAULT_CITY, city_hashtag, series_from_state

    series = series or series_from_state({})
    city = city or DEFAULT_CITY
    display = _CITY_DISPLAY.get(city.lower(), city)
    tag_city = city_hashtag(city)
    if series.id == "devfest":
        return f"DevFest {display}", (
            f"#DevFest{tag_city}",
            f"#GDG{tag_city}",
            "#GDG",
            "#GoogleDevelopersGroup",
            "#TechCommunity",
        )
    return f"{series.name} {display}", (series.hashtag, f"#GDG{tag_city}", "#GDG", "#TechCommunity")


def event_from_state(state: Any, series: Any = None, city: str = "") -> EventProfile:
    """Event profile from the session state (event_* keys), falling back to env defaults and
    to a name and hashtags derived from the selected event series and community city."""
    state = state if state is not None else {}
    if series is None:
        from agents.common.event_series import series_from_state

        series = series_from_state(state)
    default_name, default_tags = default_name_and_tags(series, city)
    website = normalise_url(_get(state, "event_website", "eventWebsite") or os.getenv("EVENT_WEBSITE", DEFAULT_WEBSITE))
    hashtags = parse_hashtags(_get(state, "event_hashtags", "eventHashtags") or os.getenv("EVENT_HASHTAGS", ""))
    profiles = parse_profiles(_get(state, "social_profiles", "socialProfiles"))
    if profiles is not None:
        # Settings → Social networks decide; no network ticked for posts means no countdown posts.
        posting = {p.network for p in profiles if p.post and p.plannable}
        channels = tuple(c for c in KNOWN_CHANNELS if c in posting)
    else:
        channels = parse_channels(_get(state, "social_channels", "socialChannels"))
    return EventProfile(
        name=str(_get(state, "event_name", "eventName") or os.getenv("EVENT_NAME", "") or default_name).strip(),
        date=parse_date(_get(state, "event_date", "eventDate") or os.getenv("EVENT_DATE", "")),
        website=website or DEFAULT_WEBSITE,
        registration_url=normalise_url(_get(state, "event_registration_url", "eventRegistrationUrl") or ""),
        venue=str(_get(state, "event_venue", "eventVenue") or os.getenv("EVENT_VENUE", "")).strip(),
        highlights=str(_get(state, "event_highlights", "eventHighlights") or "").strip(),
        hashtags=hashtags or default_tags,
        channels=channels,
        profiles=profiles or (),
        countdown=str(_get(state, "countdown_plan", "countdownPlan") or "").strip(),
    )
