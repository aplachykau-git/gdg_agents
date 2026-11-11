"""Countdown post plan: which teaser goes out when, and on which network.

A predefined sequence of milestones ("30 days to go: save the date", ...) is turned into dated
slots for the configured event. For every slot the planner picks the networks enabled in the event profile
(LinkedIn, Instagram, Facebook, X, Threads, Bluesky, Mastodon) with a short reason, from three
signals:

* topic fit: professional angles (tracks, mentoring, partners) suit LinkedIn; visual and
  atmosphere angles (venue, lounge, behind the scenes, "tomorrow") suit Instagram;
* cadence: at most ``LINKEDIN_PER_WEEK`` LinkedIn posts in any 7 days, so the feed is not spammed;
  the weakest-fit LinkedIn slot in a crowded week moves to Instagram only;
* urgency: in the last days Instagram stories carry the countdown every day;
* short-text networks (X, Threads, Bluesky, Mastodon) get a brief update on most slots.

The model then writes the texts; :func:`validate_posts` checks them against the platform rules
before they are shown as a card.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, replace
from typing import Any, Iterable

from agents.common.event_profile import EventProfile

LINKEDIN_PER_WEEK = 3
CHANNEL_FIT_THRESHOLD = 0.5

PLATFORM_RULES = {
    "linkedin": {"max_chars": 3000, "hashtags": (3, 7), "visible_chars": 210, "link": "inline"},
    "instagram": {"max_chars": 2200, "hashtags": (5, 12), "visible_chars": 125, "link": "bio"},
    "facebook": {"max_chars": 5000, "hashtags": (1, 3), "visible_chars": 480, "link": "inline"},
    "x": {"max_chars": 280, "hashtags": (1, 2), "visible_chars": 280, "link": "inline"},
    "threads": {"max_chars": 500, "hashtags": (0, 1), "visible_chars": 500, "link": "inline"},
    "bluesky": {"max_chars": 300, "hashtags": (0, 2), "visible_chars": 300, "link": "inline"},
    "mastodon": {"max_chars": 500, "hashtags": (1, 4), "visible_chars": 500, "link": "inline"},
}
SHORT_TEXT_NETWORKS = ("x", "threads", "bluesky", "mastodon")
LABELS = {
    "linkedin": "LinkedIn",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "x": "X",
    "threads": "Threads",
    "bluesky": "Bluesky",
    "mastodon": "Mastodon",
}


@dataclass(frozen=True)
class Milestone:
    days: int
    theme: str
    angle: str
    visual: str
    linkedin: float  # topic fit 0..1
    instagram: float


DEFAULT_SEQUENCE: tuple[Milestone, ...] = (
    Milestone(
        30,
        "Save the date",
        "Announce the date, the city and the venue; one line on what DevFest is; registration is free but places are limited.",
        "Key visual with the date and the venue name",
        0.9,
        0.8,
    ),
    Milestone(
        21,
        "Why attend",
        "What people take home: tracks (AI, agents, cloud, mobile, web), two stages, meeting the local community.",
        "Carousel: one slide per track",
        0.9,
        0.6,
    ),
    Milestone(
        14,
        "Hands-on workshops",
        "Learn by building: hands-on workshops, bring a laptop, limited seats.",
        "Photo of laptops and people coding together",
        0.8,
        0.6,
    ),
    Milestone(
        12,
        "Agenda is live",
        "The agenda is published: formats (talks, workshops) and topics (AI, Cloud, Web, Android); invite people to pick their sessions.",
        "Agenda screenshot or a grid of session topics",
        0.9,
        0.6,
    ),
    Milestone(
        10,
        "Community spaces",
        "Beyond the talks: lounge areas, hallway track, coding together, meeting other developers.",
        "Short reel walking through the community spaces",
        0.4,
        0.9,
    ),
    Milestone(
        7,
        "One week to go",
        "A week left: agenda highlights and a reminder to register before places run out.",
        "Countdown graphic with a big 7",
        0.8,
        0.8,
    ),
    Milestone(
        5,
        "Mentoring and careers",
        "Mentoring sessions, career and leadership talks: why it is worth coming at any career stage.",
        "Quote card from a mentor or organiser",
        0.9,
        0.4,
    ),
    Milestone(
        3,
        "Venue and getting there",
        "Where it is, how to get there, what time doors open, what to bring.",
        "Venue photo with a map pin",
        0.4,
        0.9,
    ),
    Milestone(
        2,
        "Thank you, partners",
        "Thank the partners and the volunteers who make the free event possible.",
        "Partner logo wall",
        0.9,
        0.5,
    ),
    Milestone(
        1,
        "See you tomorrow",
        "Last call: final agenda, doors-open time, badge pick-up, and the hashtag to use.",
        "Behind-the-scenes photo of the venue being prepared",
        0.6,
        0.9,
    ),
    Milestone(
        0,
        "It is today",
        "Doors are open: live updates, where to find the stages, invite people to share with the event hashtag.",
        "Story with a live photo from the entrance",
        0.5,
        1.0,
    ),
)

_KEYWORD_FIT = (
    # (keywords, linkedin, instagram)
    (
        ("venue", "location", "getting there", "map", "photo", "behind", "lounge", "space", "swag", "atmosphere"),
        0.4,
        0.9,
    ),
    (("today", "tomorrow", "live", "doors"), 0.6, 1.0),
    (("speaker", "agenda", "track", "mentor", "career", "partner", "sponsor", "workshop", "talk", "why"), 0.9, 0.5),
)


def _fit_for(theme: str) -> tuple[float, float]:
    text = theme.lower()
    for words, linkedin, instagram in _KEYWORD_FIT:
        if any(w in text for w in words):
            return linkedin, instagram
    return 0.7, 0.7


_LINE = re.compile(r"^\s*[-*•]?\s*(?:T\s*-\s*)?(\d{1,3})\s*(?:d|days?)?\s*[:|—–-]+\s*(.+?)\s*$", re.IGNORECASE)


def parse_sequence(text: str) -> tuple[Milestone, ...]:
    """Milestones from the event profile: one "days: theme" line each, e.g. "14: Hands-on workshops".

    Themes matching a default milestone keep its angle, visual and channel fit; new themes get a
    fit from keywords. Returns the default sequence when the text has no valid line.
    """
    defaults = {m.theme.lower(): m for m in DEFAULT_SEQUENCE}
    by_days = {m.days: m for m in DEFAULT_SEQUENCE}
    out: dict[int, Milestone] = {}
    for line in (text or "").splitlines():
        match = _LINE.match(line)
        if not match:
            continue
        days, theme = int(match.group(1)), match.group(2).strip()
        base = defaults.get(theme.lower())
        if base is None and days in by_days and by_days[days].theme.lower() in theme.lower():
            base = by_days[days]
        if base is not None:
            out[days] = replace(base, days=days, theme=theme)
        else:
            linkedin, instagram = _fit_for(theme)
            out[days] = Milestone(days, theme, theme, "", linkedin, instagram)
    if not out:
        return DEFAULT_SEQUENCE
    return tuple(sorted(out.values(), key=lambda m: -m.days))


def sequence_text(sequence: Iterable[Milestone] = DEFAULT_SEQUENCE) -> str:
    return "\n".join(f"{m.days}: {m.theme}" for m in sequence)


def _label(days: int) -> str:
    if days == 0:
        return "Today"
    if days == 1:
        return "Tomorrow"
    return f"{days} days to go"


def _instagram_format(m: Milestone) -> str:
    if m.days <= 1:
        return "story"
    if "carousel" in m.visual.lower():
        return "carousel"
    if "reel" in m.visual.lower():
        return "reel"
    return "feed post"


def _ordered(channels: Iterable[str]) -> list[str]:
    return [n for n in PLATFORM_RULES if n in set(channels)]


def _fit(m: Milestone, network: str) -> float:
    if network == "linkedin":
        return m.linkedin
    if network == "instagram":
        return m.instagram
    if network == "facebook":
        return round((m.linkedin + m.instagram) / 2, 2)
    return round(max(m.linkedin, m.instagram) * 0.85, 2)  # short-text networks: post often, keep it brief


def _pick(m: Milestone, network: str, force: bool = False) -> dict | None:
    """The channel entry for one network, or None when the topic does not fit it."""
    fit = _fit(m, network)
    if network == "instagram":
        if not force and fit < CHANNEL_FIT_THRESHOLD and m.days > 3:
            return None
        fmt = _instagram_format(m)
        reason = (
            "Final days: a story keeps the countdown visible every day."
            if fmt == "story"
            else f"Visual angle that works as an Instagram {fmt}."
        )
        return {"platform": network, "format": fmt, "fit": fit, "reason": reason}
    if not force and fit < CHANNEL_FIT_THRESHOLD:
        return None
    if network == "linkedin":
        return {
            "platform": network,
            "format": "text post with image or video",
            "fit": fit,
            "reason": "Professional angle that fits the LinkedIn audience.",
        }
    if network == "facebook":
        return {
            "platform": network,
            "format": "post with image",
            "fit": fit,
            "reason": "Community audience: works as a post with an image and the link.",
        }
    limit = PLATFORM_RULES[network]["max_chars"]
    return {
        "platform": network,
        "format": f"short post (up to {limit} characters)",
        "fit": fit,
        "reason": f"Fast-moving feed: a short {LABELS[network]} update keeps the countdown visible.",
    }


def build_schedule(
    event: EventProfile,
    today: dt.date,
    sequence: Iterable[Milestone] | None = None,
    linkedin_per_week: int = LINKEDIN_PER_WEEK,
) -> dict:
    """Dated countdown slots with the chosen networks, formats and reasons."""
    if event.date is None:
        raise ValueError("The event date is not set. Ask the user for it (update_event_profile).")
    sequence = tuple(sequence or parse_sequence(event.countdown))
    channels = set(event.channels)
    if not channels:
        raise ValueError("No network is enabled for posts. Ask the user where to post (update_event_profile).")

    slots: list[dict] = []
    skipped: list[dict] = []
    for m in sequence:
        when = event.date - dt.timedelta(days=m.days)
        if when < today:
            skipped.append({"days": m.days, "theme": m.theme, "date": when.isoformat()})
            continue
        picks = [p for p in (_pick(m, network) for network in _ordered(channels)) if p]
        if not picks and channels:
            options = [_pick(m, network, force=True) for network in _ordered(channels)]
            best = max(options, key=lambda p: p["fit"])
            best["reason"] = "Best available network for this topic."
            picks = [best]
        slots.append(
            {
                "id": f"d{m.days}",
                "date": when.isoformat(),
                "weekday": when.strftime("%A"),
                "days_left": m.days,
                "label": _label(m.days),
                "theme": m.theme,
                "angle": m.angle,
                "visual": m.visual,
                "channels": picks,
            }
        )

    slots.sort(key=lambda s: s["date"])
    _limit_linkedin(slots, linkedin_per_week, keep_instagram="instagram" in channels)

    rules = {p: PLATFORM_RULES[p] for p in _ordered(channels)}
    return {
        "event": {
            "name": event.name,
            "date": event.date.isoformat(),
            "website": event.website,
            "cta_url": event.cta_url,
            "venue": event.venue,
            "hashtags": list(event.hashtags),
            "profiles": [
                {"network": p.network, "label": p.label, "url": p.url, "handle": p.handle}
                for p in event.profiles
                if p.url
            ],
        },
        "today": today.isoformat(),
        "slots": slots,
        "skipped": skipped,
        "rules": rules,
    }


def _limit_linkedin(slots: list[dict], per_week: int, keep_instagram: bool) -> None:
    """Keep at most ``per_week`` LinkedIn posts in any 7-day window; move the weakest fit away."""
    if per_week <= 0:
        return
    while True:
        dated = [
            (dt.date.fromisoformat(s["date"]), s, c)
            for s in slots
            for c in s["channels"]
            if c["platform"] == "linkedin"
        ]
        crowded = None
        for start, _, _ in dated:
            window = [d for d in dated if start <= d[0] < start + dt.timedelta(days=7)]
            if len(window) > per_week:
                crowded = window
                break
        if not crowded:
            return
        # Never drop the first and last milestone of the window if there is a weaker one.
        _, slot, channel = min(crowded, key=lambda d: (d[2]["fit"], -d[1]["days_left"]))
        slot["channels"].remove(channel)
        if not any(c["platform"] == "instagram" for c in slot["channels"]) and keep_instagram:
            slot["channels"].append(
                {
                    "platform": "instagram",
                    "format": "story",
                    "fit": channel["fit"],
                    "reason": f"LinkedIn already has {per_week} posts this week; a story keeps the countdown going.",
                }
            )
        else:
            for c in slot["channels"]:
                c["reason"] += f" LinkedIn skipped: already {per_week} posts this week."
        if not slot["channels"]:
            slots.remove(slot)


_HASHTAG = re.compile(r"(?<!\w)#\w+", re.UNICODE)
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_BROKEN_TAG = re.compile(r"(#\w+)#(?!\w)", re.UNICODE)
_PLACEHOLDER = re.compile(r"\[(?:[A-Z ]*\s)?LINK\]", re.IGNORECASE)
_COUNTDOWN_NUMBER = re.compile(r"\b(\d{1,3})\s+DAYS?\b(?=[^\n]{0,40}\b(?:TO|LEFT|UNTIL|BEFORE|GO)\b)", re.IGNORECASE)


def _domain(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url or "", flags=re.IGNORECASE).rstrip("/").lower()


def _split_hashtag_block(text: str) -> tuple[str, list[str]]:
    """Separate the trailing lines that contain only hashtags from the post body."""
    lines = text.strip().splitlines()
    block: list[str] = []
    while lines and lines[-1].strip() and not _HASHTAG.sub("", lines[-1]).strip(" \t·,|"):
        block = _HASHTAG.findall(lines.pop()) + block
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip(), block


def validate_posts(schedule: dict, posts: Iterable[dict]) -> dict:
    """Attach written posts to their slots and check them against the platform rules.

    Fixes what is safe to fix (adds the website link on LinkedIn, the "link in bio" hint and the
    event hashtags), and reports the rest as warnings on the post.
    """
    event = schedule["event"]
    cta = event.get("cta_url") or event.get("website") or ""
    event_tags = event.get("hashtags") or []
    by_slot = {s["id"]: s for s in schedule["slots"]}
    for slot in by_slot.values():
        slot["posts"] = {}

    unknown: list[str] = []
    for post in posts or []:
        if not isinstance(post, dict):
            continue
        slot = by_slot.get(str(post.get("slot_id") or ""))
        platform = str(post.get("platform") or "").lower().strip()
        if slot is None or platform not in PLATFORM_RULES:
            unknown.append(f"{post.get('slot_id')}/{platform}")
            continue
        rules = PLATFORM_RULES[platform]
        raw_text = str(post.get("text") or "")
        warnings: list[str] = []
        fixes: list[str] = []
        raw_text, broken = _BROKEN_TAG.subn(r"\1", raw_text)
        if broken:
            fixes.append("fixed malformed hashtags")
        inline_link = rules["link"] == "inline"
        raw_text, placeholders = _PLACEHOLDER.subn(cta if inline_link else "link in bio", raw_text)
        if placeholders:
            fixes.append("filled link placeholders")
        for number in _COUNTDOWN_NUMBER.findall(raw_text):
            if int(number) != slot["days_left"]:
                warnings.append(
                    f'The text says "{number} days" but this post is {slot["days_left"]} days before the event.'
                )
                break
        body, block_tags = _split_hashtag_block(raw_text)
        inline_tags = _HASHTAG.findall(body)

        def seen(tag: str, pool: list[str]) -> bool:
            return tag.lower() in {t.lower() for t in pool}

        tail: list[str] = []
        for tag in block_tags + [t if str(t).startswith("#") else f"#{t}" for t in (post.get("hashtags") or [])]:
            if not seen(tag, tail) and not seen(tag, inline_tags):
                tail.append(tag)
        if event_tags and not seen(event_tags[0], tail) and not seen(event_tags[0], inline_tags):
            tail.append(event_tags[0])
            fixes.append(f"added {event_tags[0]}")
        low, high = rules["hashtags"]
        if len(inline_tags) + len(tail) > high:
            primary_tag = event_tags[0].lower() if event_tags else ""
            primary = [t for t in tail if t.lower() == primary_tag]
            others = [t for t in tail if t not in primary]
            # Inline tags count too: on short networks drop extra inline ones from the end.
            budget = max(0, high - len(primary))
            while len(inline_tags) > budget:
                removable = [t for t in inline_tags if t.lower() != primary_tag]
                if not removable:
                    break
                tag = removable[-1]
                inline_tags.remove(tag)
                body = re.sub(rf"\s*{re.escape(tag)}(?!\w)(?!.*{re.escape(tag)}(?!\w))", "", body, count=1, flags=re.S)
            keep = max(0, budget - len(inline_tags))
            tail = others[:keep] + primary
            fixes.append(f"trimmed hashtags to {high}")
        if len(inline_tags) + len(tail) < low:
            warnings.append(f"{LABELS[platform]} works best with {low}-{high} hashtags.")

        urls = _URL.findall(body)
        if inline_link:
            if cta and not any(_domain(cta) in _domain(u) or _domain(u) in _domain(cta) for u in urls):
                body = f"{body}\n\n{cta}"
                fixes.append("added the website link")
        else:
            if urls:
                for u in urls:
                    body = body.replace(u, "")
                body = re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", body)).strip()
                fixes.append("removed links (not clickable in captions)")
            if "bio" not in body.lower():
                body = f"{body}\n\nLink in bio."
                fixes.append('added "Link in bio"')

        final_text = f"{body.rstrip()}\n\n{' '.join(tail)}".strip() if tail else body.strip()
        all_tags = inline_tags + tail

        first_line = final_text.split("\n", 1)[0]
        if len(first_line) > rules["visible_chars"]:
            warnings.append(
                f'The first line is {len(first_line)} characters; only about {rules["visible_chars"]} show before "more".'
            )
        if len(final_text) > rules["max_chars"]:
            warnings.append(f"{len(final_text)} characters, over the {rules['max_chars']} limit.")

        slot["posts"][platform] = {
            "platform": platform,
            "text": final_text,
            "visual": str(post.get("visual") or slot.get("visual") or "").strip(),
            "chars": len(final_text),
            "hashtags": all_tags,
            "fixes": fixes,
            "warnings": warnings,
        }

    missing_posts = [
        f"{s['id']}/{c['platform']}"
        for s in schedule["slots"]
        for c in s["channels"]
        if c["platform"] not in s["posts"]
    ]
    counts = {p: sum(1 for s in schedule["slots"] if p in s["posts"]) for p in schedule.get("rules") or PLATFORM_RULES}
    return {
        **schedule,
        "counts": counts,
        "missing": missing_posts,
        "unknown": unknown,
        "csv": plan_csv(schedule),
    }


def _csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return f'"{text.replace(chr(34), chr(34) * 2)}"' if re.search(r'[",\n;]', text) else text


def plan_csv(schedule: dict) -> str:
    """Plan as CSV (Date, Days left, Theme, Platform, Format, Text, Visual, Reason) for Sheets."""
    rows = [
        [
            "Date",
            "Weekday",
            "Days left",
            "Theme",
            "Platform",
            "Format",
            "Text",
            "Visual idea",
            "Why this network",
            "Status",
        ]
    ]
    for slot in schedule["slots"]:
        for channel in slot["channels"]:
            post = (slot.get("posts") or {}).get(channel["platform"], {})
            rows.append(
                [
                    slot["date"],
                    slot["weekday"],
                    slot["days_left"],
                    slot["theme"],
                    LABELS.get(channel["platform"], channel["platform"]),
                    channel["format"],
                    post.get("text", ""),
                    post.get("visual") or slot.get("visual", ""),
                    channel["reason"],
                    "Draft" if post else "To write",
                ]
            )
    return "\n".join(",".join(_csv_cell(v) for v in row) for row in rows) + "\n"
