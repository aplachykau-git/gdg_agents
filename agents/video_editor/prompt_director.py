from __future__ import annotations

import concurrent.futures
import json
import os
import re
import time
from typing import Any, Sequence

from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

from agents.gemini_config import get_gemini_client

from .genre_scout import GenreBrief, scout_creative_genres
from .workflow_models import CreativeScenario, ScenarioStyle, VideoShot

PROMPT_DIRECTOR_MODEL = os.getenv("VIDEO_PROMPT_DIRECTOR_MODEL", "gemini-3.8-flash")

FORBIDDEN_TERMS = [
    "public speaking",
    "conference hall",
    "stage",
    "podium",
    "microphone",
    "auditorium",
    "audience",
    "presentation slides",
    "speaker stand",
    "keynote speaker",
    "lecture",
]

PROMPT_DIRECTOR_INSTRUCTION = """You are an elite creative director specializing in iconic high-end commercials, Super Bowl teasers, luxury brand campaigns (Apple, Nike, Porsche, Vogue, Dyson), stylized cinematic trailers, and imaginative visual spectacles.
Your task is to transform a speaker's talk topic, title, and bio into 5 wildly imaginative narrative video scenarios with completely contrasting aesthetics and vibes.
For EACH of the 5 scenarios, you will also provide 3 switchable stylistic aesthetics (so 5 narrative storylines x 3 styles = 15 total visual styles).

CRITICAL RULES:
1. PROTAGONIST: The person from the portrait photo is the hero/protagonist of the mini-film. Do NOT critique, analyze, or evaluate their facial features, clothing, or the original background of the photo.
2. ABSOLUTELY NO PUBLIC SPEAKING: Strictly avoid any conference stages, presentation podiums, lecture halls, audiences, microphones, slide decks, or classroom settings.
3. VAST TONAL DIVERSITY ACROSS SCENARIOS (RICH 5-PILLAR SPECTRUM):
   The 5 options MUST NEVER share the same genre or mood. You MUST deliver 5 completely contrasting creative worlds and advertising vibes:
   - Option 1: Grounded Human Realism / European Cinema / Cozy Artisanal (warm living world, French New Wave naturalism, cafe or workshop)
   - Option 2: Classic Comedy / Whimsical Slapstick / Playful Commercial (visual humor, eccentric Rube Goldberg contraptions, Jacques Tati / Buster Keaton timing, Wes Anderson pastel symmetry, or playful advertising parody)
   - Option 3: Auteur Arthouse / High-Energy Dynamic / Poetic Realism (Scandinavian deadpan irony, high-velocity sports motivation, Wong Kar-wai neon poetry, or lyrical magical realism)
   - Option 4: Visionary Solarpunk / Prismatic Future / Luminous Eco-Utopian (levitating crystalline prisms, solar monoliths, lush bio-architecture, clean optimism, floating kinetic light sculptures)
   - Option 5: Constructivist Mechanical / Steampunk / Industrial Allegory (colossal brass and steel clockwork, counterweights, flywheels, athletic hoist, risograph halftone textures, power & momentum)
4. METAPHORICAL CONNECTION: Creatively translate the abstract themes of the talk (e.g., distributed data, neural networks, security, speed, resilience, debugging) into thrilling, memorable visual metaphors.
5. 5 SHOTS x 2 SECONDS (EXACTLY 10 SECONDS TOTAL): Each scenario must consist of exactly 5 sequential shots, exactly 2 seconds each:
   - Shot 1 (00:00 - 00:02): Hook / Entrance into the world
   - Shot 2 (00:02 - 00:04): Dynamic escalation / visual metaphor in motion
   - Shot 3 (00:04 - 00:06): Intense action / peak interaction of the protagonist
   - Shot 4 (00:06 - 00:08): Dramatic climax / revelation
   - Shot 5 (00:08 - 00:10): Hero resolve / iconic hold into the final frame
6. NO ON-SCREEN TEXT OR SUBTITLES: Video will have graphics composited separately. The visual video stream must contain no rendered text, logos, or subtitles.
7. THREE DIVERSE & BALANCED STYLES PER SCENARIO:
   For each scenario, define the core narrative plot (concept) with its 5 shots.
   Then provide 3 switchable 'styles' variations of this exact plot:
   - Style 1: Signature Vision (the bold, highly stylized aesthetic matching the scenario's primary creative genre)
   - Style 2: Clean Modern Tech / Studio Commercial ("Попроще" / Grounded Realism — sleek, approachable, high-end tech commercial or modern studio look with clean lighting, natural skin tones, and professional elegance, avoiding surreal fantasy)
   - Style 3: Dynamic Cinematic Realism / Contrasting Movement (a distinct cinematic aesthetic such as 35mm film grain, high-energy kinetic camera, or moody atmospheric chiaroscuro)
   CRITICAL REQUIREMENT: The 5 shots MUST retain their core narrative actions across all 3 styles, but each style provides a distinct visual atmosphere, camera lenses, color grade, and omni_prompt.
   NEVER use generic placeholder names like "Style 1" or repeat the same presets across scenarios! Give each style an evocative, descriptive name.
"""

DEFAULT_TIMINGS = [
    "00:00 - 00:02",
    "00:02 - 00:04",
    "00:04 - 00:06",
    "00:06 - 00:08",
    "00:08 - 00:10",
]


class _RawShotItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    shot_number: int | None = Field(default=None, alias="shotNumber")
    time_range: str | None = Field(default=None, alias="timeRange")
    action: str | None = None
    camera: str | None = None
    lighting_atmosphere: str | None = Field(default=None, alias="lightingAtmosphere")


class _RawScenarioStyleItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str | None = None
    name: str | None = None
    genre: str | None = None
    shots: list[Any] = Field(default_factory=list)
    omni_prompt: str | None = Field(default=None, alias="omniPrompt")


class _RawScenarioItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str | None = Field(default=None, description="Unique snake_case scenario identifier")
    title: str | None = Field(default=None, description="Catchy cinematic or commercial title")
    genre: str | None = Field(default=None, description="Distinct genre label")
    concept: str | None = Field(default=None, description="2-sentence creative storyline summary")
    narrative_metaphor: str | None = Field(
        default=None, description="How the speaker's bio/topic translates into visual action"
    )
    shots: list[Any] = Field(default_factory=list, description="5 progressive shots detailing the 10-second sequence")
    omni_prompt: str | None = Field(default=None, alias="omniPrompt", description="Complete 9:16 multi-shot prompt")
    styles: list[Any] = Field(default_factory=list, description="Switchable styles for the scenario")
    number: int | None = Field(default=None, description="Scenario option number (1..5)")


class _RawGeneratedScenarios(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scenarios: list[Any] = Field(default_factory=list)


def _normalize_shot(raw: Any, idx: int, speaker_name: str | None = None) -> VideoShot:
    """Safely convert dict/object/string into a validated VideoShot with defaults."""
    if isinstance(raw, VideoShot):
        return raw

    default_timing = DEFAULT_TIMINGS[min(idx - 1, len(DEFAULT_TIMINGS) - 1)]
    if isinstance(raw, str):
        return VideoShot(
            shot_number=idx,
            time_range=default_timing,
            action=_sanitize_scenario_text(raw, speaker_name),
            camera="Dynamic cinematic tracking shot.",
            lighting_atmosphere="Vibrant commercial atmosphere.",
        )

    if isinstance(raw, dict):
        shot_num = raw.get("shot_number") or raw.get("shotNumber") or raw.get("shot") or idx
        try:
            shot_num = int(shot_num)
        except (ValueError, TypeError):
            shot_num = idx
        time_range = str(raw.get("time_range") or raw.get("timeRange") or raw.get("timing") or default_timing)
        action = str(
            raw.get("action")
            or raw.get("description")
            or raw.get("visual")
            or raw.get("prompt")
            or raw.get("scene")
            or f"The protagonist drives the action in shot {idx}."
        )
        camera = str(
            raw.get("camera") or raw.get("camera_movement") or raw.get("movement") or "Dynamic cinematic tracking shot."
        )
        lighting = str(
            raw.get("lighting_atmosphere")
            or raw.get("lightingAtmosphere")
            or raw.get("lighting")
            or raw.get("atmosphere")
            or raw.get("color_grade")
            or "Vibrant commercial atmosphere."
        )
        return VideoShot(
            shot_number=shot_num,
            time_range=time_range,
            action=_sanitize_scenario_text(action, speaker_name),
            camera=_sanitize_scenario_text(camera, speaker_name),
            lighting_atmosphere=_sanitize_scenario_text(lighting, speaker_name),
        )

    shot_num = getattr(raw, "shot_number", None) or getattr(raw, "shotNumber", None) or idx
    try:
        shot_num = int(shot_num)
    except (ValueError, TypeError):
        shot_num = idx
    time_range = str(getattr(raw, "time_range", None) or getattr(raw, "timeRange", None) or default_timing)
    action = str(
        getattr(raw, "action", None)
        or getattr(raw, "description", None)
        or f"The protagonist drives the action in shot {idx}."
    )
    camera = str(getattr(raw, "camera", None) or "Dynamic cinematic tracking shot.")
    lighting = str(
        getattr(raw, "lighting_atmosphere", None)
        or getattr(raw, "lightingAtmosphere", None)
        or "Vibrant commercial atmosphere."
    )
    return VideoShot(
        shot_number=shot_num,
        time_range=time_range,
        action=_sanitize_scenario_text(action, speaker_name),
        camera=_sanitize_scenario_text(camera, speaker_name),
        lighting_atmosphere=_sanitize_scenario_text(lighting, speaker_name),
    )


def _extract_shots_from_text_or_prompt(text: str, speaker_name: str | None = None) -> list[VideoShot]:
    """Attempts to parse progressive 5 shots from an omni prompt or raw string."""
    if not text:
        return []
    pattern = re.compile(
        r"(?:Shot\s*(\d+)|\b(\d+)\b)\s*(?:\(([^)]+)\)|\[([^\]]+)\])?\s*[:\-–]\s*([^\n]+?)(?=(?:Shot\s*\d+|\b\d+\s*\(|\n\n|$))",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    shots = []
    for s_idx, m in enumerate(matches, start=1):
        num_str = m.group(1) or m.group(2) or str(s_idx)
        time_str = m.group(3) or m.group(4) or DEFAULT_TIMINGS[min(s_idx - 1, len(DEFAULT_TIMINGS) - 1)]
        action = m.group(5).strip()
        if action:
            shots.append(
                VideoShot(
                    shot_number=int(num_str) if num_str.isdigit() else s_idx,
                    time_range=time_str.strip(),
                    action=_sanitize_scenario_text(action, speaker_name),
                    camera="Dynamic cinematic camera tracking.",
                    lighting_atmosphere="Cinematic atmospheric lighting.",
                )
            )
        if len(shots) == 5:
            break
    return shots


def _normalize_scenario_item(entry: Any, idx: int, speaker_name: str | None = None) -> CreativeScenario | None:
    """Robustly normalize a raw scenario dictionary or model into a valid CreativeScenario."""
    if isinstance(entry, CreativeScenario):
        has_timing = any(marker in entry.omni_prompt.lower() for marker in ("00:00", "0-2s", "shot 1", "shot 2"))
        if not has_timing and entry.shots:
            entry.omni_prompt = format_timed_omni_prompt(entry.shots, entry.genre, entry.omni_prompt)
        return _ensure_scenario_styles(entry)

    if not isinstance(entry, dict):
        if hasattr(entry, "model_dump"):
            entry = entry.model_dump()
        elif hasattr(entry, "__dict__"):
            entry = entry.__dict__
        else:
            return None

    sc_id = str(entry.get("id") or f"scenario_{idx}")
    title = str(entry.get("title") or f"Creative Concept {idx}")
    genre = str(entry.get("genre") or "Cinematic Commercial")
    raw_metaphor = entry.get("narrative_metaphor") or entry.get("narrativeMetaphor")
    narrative_metaphor = _sanitize_scenario_text(str(raw_metaphor), speaker_name) if raw_metaphor else None

    # Extract shots: look for shots under common keys
    raw_shots = (
        entry.get("shots")
        or entry.get("storyboard")
        or entry.get("scenes")
        or entry.get("shot_list")
        or entry.get("timeline")
        or []
    )
    raw_styles = entry.get("styles") or []

    if not raw_shots and raw_styles and isinstance(raw_styles, list):
        first_style = raw_styles[0]
        if isinstance(first_style, dict):
            raw_shots = first_style.get("shots") or first_style.get("storyboard") or first_style.get("scenes") or []
        elif hasattr(first_style, "shots"):
            raw_shots = getattr(first_style, "shots", [])

    shots = [_normalize_shot(sh, s_idx, speaker_name) for s_idx, sh in enumerate(raw_shots, start=1)]

    # If shots are missing or empty, attempt extraction from omni_prompt or description
    if not shots:
        omni_candidate = str(entry.get("omni_prompt") or entry.get("omniPrompt") or entry.get("prompt") or "")
        if omni_candidate:
            shots = _extract_shots_from_text_or_prompt(omni_candidate, speaker_name)

    # If shots are missing or fewer than 5, fill progressive contextual shots tailored to the genre
    if len(shots) < 5:
        contextual_actions = [
            f"The protagonist enters the world of {genre}, engaging with the atmosphere.",
            f"The protagonist initiates a pivotal action, setting {narrative_metaphor.lower() if narrative_metaphor else 'the narrative'} in motion.",
            "At the center of the action, the protagonist maneuvers complex elements with confident mastery.",
            "The entire scene transforms dramatically as the core mechanism reaches peak intensity.",
            "The protagonist holds an iconic hero stance amid the transformed space into the final frame.",
        ]
        while len(shots) < 5:
            s_idx = len(shots) + 1
            action_text = contextual_actions[min(s_idx - 1, len(contextual_actions) - 1)]
            shots.append(
                VideoShot(
                    shot_number=s_idx,
                    time_range=DEFAULT_TIMINGS[min(s_idx - 1, len(DEFAULT_TIMINGS) - 1)],
                    action=action_text,
                    camera="Dynamic cinematic camera move with dramatic depth of field.",
                    lighting_atmosphere="Rich volumetric lighting and cinematic atmosphere.",
                )
            )

    # Narrative storyline concept (plot synopsis): ensure rich, non-placeholder description
    raw_concept = entry.get("concept") or entry.get("storyline") or entry.get("plot") or entry.get("description")
    concept_candidate = _sanitize_scenario_text(str(raw_concept).strip(), speaker_name) if raw_concept else ""
    if not concept_candidate or concept_candidate.lower() in (
        "a high-concept visual story.",
        "a high-concept visual story",
    ):
        if shots and len(shots) >= 3:
            action1 = shots[0].action.rstrip(".")
            action_climax = shots[3].action.rstrip(".") if len(shots) > 3 else shots[-1].action.rstrip(".")
            concept = f"In this {genre.lower()} sequence, {action1.lower()}, culminating as {action_climax.lower()}."
        elif narrative_metaphor:
            concept = f"Set in a {genre.lower()} universe where {narrative_metaphor.lower()}."
        else:
            concept = f"A high-velocity 10-second cinematic sequence in a {genre.lower()} universe."
    else:
        concept = concept_candidate

    omni_prompt = str(entry.get("omni_prompt") or entry.get("omniPrompt") or "")
    if not omni_prompt and raw_styles and isinstance(raw_styles, list):
        first_st = raw_styles[0]
        omni_prompt = str(
            (first_st.get("omni_prompt") or first_st.get("omniPrompt"))
            if isinstance(first_st, dict)
            else (getattr(first_st, "omni_prompt", None) or "")
        )

    has_timing = any(marker in omni_prompt.lower() for marker in ("00:00", "0-2s", "shot 1", "shot 2"))
    if not has_timing or not omni_prompt:
        omni_prompt = format_timed_omni_prompt(shots, genre, omni_prompt)
    else:
        omni_prompt = _sanitize_scenario_text(omni_prompt, speaker_name)

    # Process styles if provided
    styles: list[ScenarioStyle] = []
    if raw_styles and isinstance(raw_styles, list):
        for st_idx, st_raw in enumerate(raw_styles, start=1):
            if isinstance(st_raw, dict):
                st_id = str(st_raw.get("id") or f"{sc_id}_style_{st_idx}")
                st_name = _sanitize_scenario_text(str(st_raw.get("name") or f"Style {st_idx}"), speaker_name)
                st_genre = _sanitize_scenario_text(str(st_raw.get("genre") or genre), speaker_name)
                st_shots_raw = st_raw.get("shots") or shots
                st_shots = [
                    _normalize_shot(sh, sh_idx, speaker_name) for sh_idx, sh in enumerate(st_shots_raw, start=1)
                ]
                st_prompt = str(st_raw.get("omni_prompt") or st_raw.get("omniPrompt") or "")
                if not any(marker in st_prompt.lower() for marker in ("00:00", "0-2s", "shot 1", "shot 2")):
                    st_prompt = format_timed_omni_prompt(st_shots, st_genre, st_prompt)
                st_prompt = _sanitize_scenario_text(st_prompt, speaker_name)
                styles.append(
                    ScenarioStyle(id=st_id, name=st_name, genre=st_genre, shots=st_shots, omni_prompt=st_prompt)
                )
            elif isinstance(st_raw, str):
                st_id = f"{sc_id}_style_{st_idx}"
                st_name = _sanitize_scenario_text(st_raw, speaker_name)
                st_genre = _sanitize_scenario_text(st_raw, speaker_name)
                st_shots = list(shots)
                st_prompt = _sanitize_scenario_text(format_timed_omni_prompt(st_shots, st_genre), speaker_name)
                styles.append(
                    ScenarioStyle(id=st_id, name=st_name, genre=st_genre, shots=st_shots, omni_prompt=st_prompt)
                )
            elif hasattr(st_raw, "id"):
                styles.append(st_raw)

    sc = CreativeScenario(
        id=sc_id,
        title=title,
        genre=genre,
        concept=concept,
        narrative_metaphor=narrative_metaphor,
        shots=shots,
        omni_prompt=omni_prompt,
        styles=styles,
        number=idx,
    )
    return _ensure_scenario_styles(sc, idx)


def _sanitize_scenario_text(text: str, speaker_name: str | None = None) -> str:
    """Ensure no conference/stage terms or real personal names seep through."""
    cleaned = text
    for term in FORBIDDEN_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "cinematic space", cleaned, flags=re.IGNORECASE)
    if speaker_name and speaker_name.strip():
        # Replace full speaker name with 'the protagonist'
        cleaned = re.sub(rf"\b{re.escape(speaker_name.strip())}\b", "the protagonist", cleaned, flags=re.IGNORECASE)
        # Also replace individual name tokens >= 3 chars
        for part in speaker_name.split():
            if len(part) >= 3 and part.lower() not in {"and", "the", "van", "von", "de", "del"}:
                cleaned = re.sub(rf"\b{re.escape(part)}\b", "the protagonist", cleaned, flags=re.IGNORECASE)
        # Clean up repeated 'the protagonist'
        cleaned = re.sub(r"\bthe protagonist(?:\s+the protagonist)+\b", "the protagonist", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bthe protagonist\s*'?s\b", "the protagonist's", cleaned, flags=re.IGNORECASE)
        # Capitalize beginning of sentence or line
        cleaned = re.sub(r"(^|[:.!?]\s+)the protagonist\b", r"\1The protagonist", cleaned)
    return cleaned


def format_timed_omni_prompt(shots: Sequence[VideoShot], genre: str = "", fallback_prompt: str = "") -> str:
    """Ensure omni_prompt explicitly includes all 5 shots with timings."""
    if not shots:
        return fallback_prompt
    prefix = f"Cinematic 9:16 {genre}. " if genre else ""
    shot_parts = [
        f"Shot {sh.shot_number} ({sh.time_range}): {sh.action} Camera: {sh.camera}. Atmosphere: {sh.lighting_atmosphere}."
        for sh in sorted(shots, key=lambda s: s.shot_number)
    ]
    return prefix + " ".join(shot_parts)


def _build_fallback_scenarios(talk_title: str, speaker_name: str) -> list[CreativeScenario]:
    """Deterministic fallback scenarios providing a balanced 5-pillar spectrum:
    Option 1: Grounded Realism (French New Wave)
    Option 2: Classic Comedy (Jacques Tati Rube Goldberg)
    Option 3: High-Energy Sports (Sunrise Velocity Anthem)
    Option 4: Visionary Solarpunk (Refracted Prismatic Horizon)
    Option 5: Constructivist Mechanical (Basework of Autonomous Gears)
    """
    base_title = talk_title or "Future Technology"
    return [
        CreativeScenario(
            id="scenario_grounded_realism",
            title="The Boulevard Espresso Realism",
            genre="French New Wave / Grounded Artisanal Realism",
            concept=f"A warm, grounded indie cinema sequence where '{base_title}' unfolds in a sunlit Parisian café and bookstore, told with natural 35mm daylight, tactile espresso rituals, and intimate human charm.",
            narrative_metaphor="The protagonist connects abstract digital systems with tactile, warm daily life in an inviting European atelier.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist walks into a charming sunlit cobblestone café, taking a seat beside tall open French windows as morning light washes over the table.",
                    camera="Handheld naturalistic 35mm tracking shot moving alongside protagonist.",
                    lighting_atmosphere="Golden-hour morning daylight streaming through dust motes.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="The protagonist pulls out a worn leather notebook and pens a blueprint, while steam from a fresh porcelain espresso cup rises gracefully into the sunbeams.",
                    camera="Intimate rack-focus from the pen tip to the protagonist's thoughtful smile.",
                    lighting_atmosphere="Warm honey-toned ambient natural illumination.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="A vintage brass record player on the café counter begins spinning, its needle dropping into the groove with a soft warm crackle that brings the space alive.",
                    camera="Tactile macro close-up of the vinyl needle and revolving record.",
                    lighting_atmosphere="Rich Kodak 35mm warmth with deep amber tones.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="Outside the window, the lively city street flows harmoniously as neighbors, bicycles, and flower carts move in cheerful, synchronized rhythm.",
                    camera="Gentle lateral pan following a bicycle past the sunlit window frame.",
                    lighting_atmosphere="Natural European daylight with pastel awnings and cobblestone reflections.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="The protagonist takes a calm sip of espresso, closes the notebook with a contented glance toward the camera, ready for the day.",
                    camera="Warm medium portrait hold, gentle natural camera breathing into the final frame.",
                    lighting_atmosphere="Soft flattering window light with creamy natural bokeh.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 French New Wave grounded artisanal realism. "
                "Shot 1 (00:00 - 00:02): Handheld 35mm tracking of protagonist entering a sunlit cobblestone Parisian café. "
                "Shot 2 (00:02 - 00:04): Intimate rack-focus from pen drafting a blueprint to rising espresso steam in sunbeams. "
                "Shot 3 (00:04 - 00:06): Tactile macro close-up of a vintage vinyl needle dropping onto spinning record. "
                "Shot 4 (00:06 - 00:08): Gentle lateral pan of a vibrant European street with bicycles and flower carts. "
                "Shot 5 (00:08 - 00:10): Warm medium portrait hold of protagonist taking a calm sip of espresso into camera."
            ),
        ),
        CreativeScenario(
            id="scenario_tati_comedy",
            title="The Clockwork Baker's Rube Goldberg",
            genre="Jacques-Tati Visual Slapstick / Whimsical Comedy",
            concept=f"A delightful, eccentric physical comedy short where '{base_title}' is represented by an elaborate Rube Goldberg baking contraption that humorously synchronizes dough, bells, and flour.",
            narrative_metaphor="Complex coordination and automation are dramatized as an eccentric, charmingly synchronized bakery mechanism with playful comedic timing.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist in a crisp baker's apron stands before an enormous, quirky wooden contraption with copper funnels and ticking dials.",
                    camera="Planimetric dead-center symmetrical wide shot, snappy comedic timing.",
                    lighting_atmosphere="Bright, cheerful pastel bakery daylight with flour dust motes.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="The protagonist taps a tiny brass bicycle bell; instantly, a wooden lever catapults a croissant dough ball into a spinning copper spiral track.",
                    camera="Rapid playful whip-pan tracking the bouncing dough through the spiral.",
                    lighting_atmosphere="Warm golden oven glow and crisp morning sunbeams.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="The dough ball lands on a miniature see-saw that pulls a cord, causing a mechanical rooster to crow and release a cloud of white powdered sugar.",
                    camera="Comedic low-angle tilt up from the see-saw to the mechanical rooster.",
                    lighting_atmosphere="High-key saturated primary colors with powdery white sugar veil.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="A conveyor belt smoothly slides a fresh tray of golden pastries out of the oven, each perfectly aligned and steaming in flawless precision.",
                    camera="Overhead top-down flat-lay tracking the sliding pastry tray in snappy motion.",
                    lighting_atmosphere="Warm golden buttery highlights and mouthwatering studio rim lighting.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="The protagonist catches a warm croissant with effortless comedic flair, brushing a smudge of flour off their nose with a triumphant deadpan wink.",
                    camera="Centered hero medium shot holding on their playful, satisfied smile.",
                    lighting_atmosphere="Radiant warm bakery glow, whimsical and charming.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 Jacques Tati whimsical physical comedy. "
                "Shot 1 (00:00 - 00:02): Symmetrical wide framing of protagonist baker before a quirky wooden Rube Goldberg contraption. "
                "Shot 2 (00:02 - 00:04): Rapid whip-pan following a catapulted dough ball through a spinning copper spiral. "
                "Shot 3 (00:04 - 00:06): Comedic tilt up as a mechanical rooster crows, puffing a cloud of powdered sugar. "
                "Shot 4 (00:06 - 00:08): Overhead flat-lay tracking a sliding tray of golden steaming croissants. "
                "Shot 5 (00:08 - 00:10): Centered hero hold catching a croissant and deadpan winking into camera."
            ),
        ),
        CreativeScenario(
            id="scenario_kinetic_anthem",
            title="The Sunrise Velocity Anthem",
            genre="High-Energy Urban Sports / Brand Commercial",
            concept=f"An electrifying, athletic motivation commercial visualizing the speed and relentless drive of '{base_title}' through an early-morning city bridge run.",
            narrative_metaphor="High performance, instant response, and endurance are embodied by an athletic sunrise sprint through an awakening metropolis.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist ties running shoes on a misty suspension bridge as the first golden rays of sunrise break through towering skyscrapers.",
                    camera="Low-angle macro push-in focusing on shoes hitting the asphalt.",
                    lighting_atmosphere="Crisp cobalt dawn sky blending into piercing golden-hour sunrise.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="The protagonist takes off in an explosive athletic sprint, breath billowing in the cool air as camera glides alongside at full speed.",
                    camera="Dynamic vehicle-mounted tracking shot racing alongside at hip height.",
                    lighting_atmosphere="Blinding horizontal lens flare slicing through suspension cables.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="Macro close-up of sweat droplets glistening on their brow, eyes focused ahead with unwavering determination and grit.",
                    camera="1000fps ultra-slow-motion floating macro tracking shot.",
                    lighting_atmosphere="Intense golden rim-lighting carving sharp silhouette against skyline.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="Reaching the crest of the bridge, the expansive city wakes beneath them as morning sunlight floods across the glass towers.",
                    camera="Sweeping drone pullback ascending rapidly over the bridge deck.",
                    lighting_atmosphere="Breathtaking golden-hour panoramic radiance across city river.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="The protagonist catches breath with hands on hips, looking out over the city with triumphant, calm power as the final frame locks.",
                    camera="Centered hero medium hold against the vast illuminated skyline.",
                    lighting_atmosphere="Heroic golden sunlight wash with crisp modern contrast.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 high-energy Nike-style urban sunrise commercial. "
                "Shot 1 (00:00 - 00:02): Low-angle push-in on protagonist tying running shoes on a misty city suspension bridge. "
                "Shot 2 (00:02 - 00:04): Fast vehicle-mounted tracking shot alongside explosive athletic sprint at dawn. "
                "Shot 3 (00:04 - 00:06): 1000fps ultra-slow-motion macro of focused eyes and glistening sweat droplets in golden flare. "
                "Shot 4 (00:06 - 00:08): Sweeping drone pullback ascending over bridge crest revealing sun-drenched skyline. "
                "Shot 5 (00:08 - 00:10): Centered hero hold of protagonist standing proud atop bridge overlooking the city."
            ),
        ),
        CreativeScenario(
            id="scenario_solarpunk_prismatic",
            title="The Refracted Solarpunk Horizon",
            genre="Visionary Solarpunk / Prismatic Future",
            concept=f"A breathtaking visionary solarpunk sequence where '{base_title}' is manifested as a luminous cathedral of floating crystalline prisms and vertical bio-gardens, refracting ideas into pure rainbow energy.",
            narrative_metaphor="The protagonist navigates and harmonizes floating crystalline prisms that refract complex ideas into brilliant, sustainable light.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist steps onto a sunlit glass sky-terrace overlooking a lush solarpunk metropolis of spiral white towers and cascading vertical flora.",
                    camera="Sweeping cinematic crane descending toward the protagonist.",
                    lighting_atmosphere="Radiant morning sunlight filtering through translucent quartz glass and emerald leaves.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="The protagonist reaches out toward a cluster of floating geometric prisms that rotate silently in zero gravity, casting rainbow caustics across the terrace.",
                    camera="Fluid 360-degree tracking arc gliding around the levitating crystalline prisms.",
                    lighting_atmosphere="Brilliant iridescent light flares and soft ethereal atmospheric bloom.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="As they touch the central prism, beams of pure refracted spectrums branch out like luminous neural pathways connecting the garden canopies.",
                    camera="Dynamic macro push-in focusing on glowing crystalline facets and sparkling light pulses.",
                    lighting_atmosphere="Vibrant spectral rainbow refractions dancing across their focused expression.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="The entire bio-architectural canopy pulses with synchronized emerald and gold light, harmonizing technology with living nature.",
                    camera="Majestic ascending drone shot revealing vast panoramic bio-domes.",
                    lighting_atmosphere="Breathtaking golden-hour radiance across pristine white and glass spires.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="The protagonist turns toward the horizon with a calm visionary smile as floating light motes swirl weightlessly into the final frame.",
                    camera="Centered hero medium hold against the radiant utopian skyline.",
                    lighting_atmosphere="Luminous golden glow with pristine crystal clarity.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 visionary solarpunk prismatic future commercial. "
                "Shot 1 (00:00 - 00:02): Sweeping crane descent on protagonist stepping onto a sunlit glass sky-terrace over a spiral bio-city. "
                "Shot 2 (00:02 - 00:04): 360-degree tracking arc around floating zero-gravity crystalline prisms casting rainbow caustics. "
                "Shot 3 (00:04 - 00:06): Dynamic macro push-in as touch ignites branching spectral light beams through garden canopies. "
                "Shot 4 (00:06 - 00:08): Majestic ascending drone reveal of synchronized pulsing emerald bio-domes at golden hour. "
                "Shot 5 (00:08 - 00:10): Centered hero hold of protagonist smiling against the radiant utopian skyline."
            ),
        ),
        CreativeScenario(
            id="scenario_constructivist_gears",
            title="The Basework of Autonomous Gears",
            genre="Constructivist Mechanical / Steampunk Allegory",
            concept=f"A monumental constructivist industrial allegory where '{base_title}' is dramatized as a subterranean cathedral of interlocking bronze gears, massive counterweights, and athletic kinetic mastery.",
            narrative_metaphor="The protagonist commands colossal mechanical gears and flywheels, transforming heavy structural complexity into effortless, unstoppable motion.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist walks along an elevated cast-iron catwalk inside a colossal subterranean chamber filled with giant soot-black steel girders and ticking bronze gears.",
                    camera="Dutch-angle low tracking shot gazing up into the monumental industrial architecture.",
                    lighting_atmosphere="Dramatic chiaroscuro with shafts of amber tungsten cutting through curling plumes of white steam.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="The protagonist approaches a massive brass master lever connected to a towering kinetic flywheel covered in fine risograph halftone patina.",
                    camera="Fast mechanical push-in toward their hand gripping the textured brass handle.",
                    lighting_atmosphere="Warm furnace embers reflecting off polished bronze teeth and oil-sheened steel.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="With deliberate athletic strength, protagonist pulls the lever; giant counterweights descend in synchronized rhythm as colossal interlocking gears spin to life.",
                    camera="Visceral low-angle whip-pan tracking spinning gears and sparking bronze teeth.",
                    lighting_atmosphere="Brilliant flashes of industrial friction sparks and deep silhouette shadows.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="The entire subterranean machinery reaches flawless mechanical harmony, its deep kinetic pulse driving a towering dynamo that illuminates the chamber.",
                    camera="Sweeping circular boom shot gliding past spinning brass cogs and steam valves.",
                    lighting_atmosphere="Radiant amber furnace glow illuminating soaring steel trusses.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="The protagonist stands composed beside the humming flywheel, resting a confident hand on the gear housing with triumphant mastery into the final frame.",
                    camera="Centered hero medium hold, framed by majestic interlocking gears.",
                    lighting_atmosphere="Warm heroic rim lighting carving a sharp silhouette against rising steam.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 constructivist mechanical steampunk industrial commercial. "
                "Shot 1 (00:00 - 00:02): Dutch-angle low tracking shot through subterranean cathedral of steel girders and giant bronze gears. "
                "Shot 2 (00:02 - 00:04): Fast push-in on protagonist gripping massive brass lever of a towering kinetic flywheel. "
                "Shot 3 (00:04 - 00:06): Visceral low whip-pan as counterweights descend and giant interlocking gears spin with sparks. "
                "Shot 4 (00:06 - 00:08): Sweeping boom shot past spinning brass cogs and steam valves in glowing furnace light. "
                "Shot 5 (00:08 - 00:10): Centered hero hold resting hand on gear housing with triumphant calm against rising steam."
            ),
        ),
    ]


def _ensure_scenario_styles(sc: CreativeScenario, idx: int = 1) -> CreativeScenario:
    """Ensure every scenario has 3 switchable style tabs adapting the same narrative plot."""
    sc_idx = getattr(sc, "number", None) or idx or 1
    if sc_idx <= 1:
        match = re.search(r"(\d+)", sc.id or "")
        if match:
            try:
                sc_idx = int(match.group(1))
            except ValueError:
                sc_idx = idx or 1

    if sc.styles and len(sc.styles) >= 3:
        names = [st.name for st in sc.styles]
        genres = [st.genre for st in sc.styles]
        has_generic_labels = all(n in ("Style 1", "Style 2", "Style 3", "Style", "") for n in names)
        has_same_genre = len(set(genres)) == 1 and genres[0] == sc.genre
        has_repeated_generic = sc_idx > 1 and any(
            re.search(r"clean modern|studio commercial|cinematic 35mm|dynamic cinematic", n, re.I) for n in names
        )
        is_all_generic = has_generic_labels or has_same_genre or has_repeated_generic
        if not is_all_generic:
            if not sc.shots and sc.styles[0].shots:
                sc.shots = sc.styles[0].shots
            if not sc.omni_prompt and sc.styles[0].omni_prompt:
                sc.omni_prompt = sc.styles[0].omni_prompt
            if not sc.genre and sc.styles[0].genre:
                sc.genre = sc.styles[0].genre
            return sc

    # Style 1: Signature Vision
    style1_name = sc.genre.split("/")[0].strip() if "/" in sc.genre else sc.genre
    style1 = ScenarioStyle(
        id=f"{sc.id}_style_1",
        name=style1_name or "Style 1 (Signature)",
        genre=sc.genre,
        shots=list(sc.shots),
        omni_prompt=sc.omni_prompt,
    )

    # Category A: Clean Modern Tech / Studio Commercial ("Попроще" / Grounded Realism)
    grounded_styles = [
        {
            "name": "Clean Modern Tech",
            "genre": "Clean Modern Tech / Studio Commercial",
            "camera": "Smooth horizontal Steadicam glide, crisp prime lens focus, balanced centered framing.",
            "lighting": "Clean soft-diffused studio key light, subtle rim reflections, authentic natural skin tones.",
        },
        {
            "name": "Architectural Daylight",
            "genre": "Architectural Daylight / Modern Editorial",
            "camera": "Expansive slow push-in, wide architectural glass reflections, elegant depth of field.",
            "lighting": "Abundant natural daylight, soft airy ambient bounce, crisp modern aesthetic.",
        },
        {
            "name": "Minimalist Keynote",
            "genre": "Minimalist Studio / Keynote Elegance",
            "camera": "Subtle cinematic slow zoom, sharp eye-level prime focus, clean editorial framing.",
            "lighting": "High-end keynote rim lighting, clean dark gradient backdrop, crisp professional skin tones.",
        },
        {
            "name": "Warm Artisanal Studio",
            "genre": "Warm Artisanal Studio / Tactile Craft",
            "camera": "Smooth handheld prime lens, gentle natural breathing, intimate framing.",
            "lighting": "Warm amber lamplight, soft window bounce, natural wood and textured linen accents.",
        },
        {
            "name": "Precision Macro Lab",
            "genre": "Precision Macro Lab / Modern Cleanroom",
            "camera": "Crisp horizontal slider glide, high-index prime focus, subtle glass reflections.",
            "lighting": "Pristine cool-white daylight bounce, delicate rim reflections, ultra-clean modern precision.",
        },
    ]

    # Category B: Dynamic Cinematic Realism / Contrasting Movement
    cinematic_styles = [
        {
            "name": "Cinematic 35mm Realism",
            "genre": "Cinematic 35mm Documentary / Kodak Film",
            "camera": "Tactile handheld Arri Alexa, organic camera breathing, subtle shallow depth of field.",
            "lighting": "Warm natural ambient lighting with gentle film halation and subtle organic grain.",
        },
        {
            "name": "High-Velocity Kinetic",
            "genre": "High-Velocity Kinetic / Dynamic Energy",
            "camera": "Rapid kinetic tracking, visceral low-angle whip-pan, sharp motion-tracking arc.",
            "lighting": "Punchy high-contrast specular lighting, deep shadows, dynamic rim highlights.",
        },
        {
            "name": "Atmospheric Neo-Noir",
            "genre": "Atmospheric Neo-Noir / Chiaroscuro",
            "camera": "Dutch angle slow tilt, anamorphic horizontal flare, reflective dark ground tracking.",
            "lighting": "Chiaroscuro moody shadows with sharp directional rim light and deep contrast.",
        },
        {
            "name": "Prismatic Technicolor",
            "genre": "Prismatic Technicolor / Saturated Spectrum",
            "camera": "Floating anamorphic lens flares, dynamic slow push-in, rich depth.",
            "lighting": "Iridescent rainbow caustics, saturated primary tones, and luminous optical bloom.",
        },
        {
            "name": "Industrial Chiaroscuro",
            "genre": "Heavy Industrial / Raw Chiaroscuro",
            "camera": "Low-angle textured tilt, visceral slow-motion pan, gritty industrial framing.",
            "lighting": "High-contrast tungsten furnace glow, deep matte shadows, and dramatic rim highlights.",
        },
    ]

    p2 = grounded_styles[(sc_idx - 1) % len(grounded_styles)]
    p3 = cinematic_styles[(sc_idx - 1) % len(cinematic_styles)]

    style2_shots = [
        VideoShot(
            shot_number=sh.shot_number,
            time_range=sh.time_range,
            action=sh.action,
            camera=p2["camera"],
            lighting_atmosphere=p2["lighting"],
        )
        for sh in sc.shots
    ]
    style2 = ScenarioStyle(
        id=f"{sc.id}_style_2",
        name=p2["name"],
        genre=p2["genre"],
        shots=style2_shots,
        omni_prompt=format_timed_omni_prompt(style2_shots, p2["genre"]),
    )

    style3_shots = [
        VideoShot(
            shot_number=sh.shot_number,
            time_range=sh.time_range,
            action=sh.action,
            camera=p3["camera"],
            lighting_atmosphere=p3["lighting"],
        )
        for sh in sc.shots
    ]
    style3 = ScenarioStyle(
        id=f"{sc.id}_style_3",
        name=p3["name"],
        genre=p3["genre"],
        shots=style3_shots,
        omni_prompt=format_timed_omni_prompt(style3_shots, p3["genre"]),
    )

    sc.styles = [style1, style2, style3]
    return sc


SHOT_DIRECTOR_INSTRUCTION = """You are an elite cinematic storyboard director, cinematographer, and visual sequence designer.
Your task is to take PRE-SELECTED, RADICALLY CONTRASTING creative genre worlds and flesh each of them out into an exact, professional 5-shot x 2-second (10 seconds total) commercial/film storyboard.

CRITICAL REQUIREMENTS:
1. STRICT ADHERENCE TO GIVEN GENRES:
   You will receive distinct genre briefs (each with an assigned Title, Genre, Visual Universe, Aesthetic Manifesto, and Narrative Metaphor).
   You MUST faithfully translate EACH pre-selected genre into its own 5-shot sequence. Do NOT homogenize or change their assigned genres or atmospheres!
2. PROTAGONIST IS THE HERO:
   The person from the photo is the active hero/protagonist of each mini-film. Do NOT critique their appearance or original photo background.
3. ABSOLUTELY NO PUBLIC SPEAKING:
   Strictly avoid conference halls, presentation podiums, lecture rooms, audiences, microphones, and slide decks.
4. EXACT 5 SHOTS x 2 SECONDS (TOTAL 10 SECONDS):
   Each scenario must consist of exactly 5 sequential progressive shots:
   - Shot 1 (00:00 - 00:02): Hook / Entrance into the world
   - Shot 2 (00:02 - 00:04): Dynamic escalation / visual metaphor in motion
   - Shot 3 (00:04 - 00:06): Intense action / peak interaction of the protagonist
   - Shot 4 (00:06 - 00:08): Dramatic climax / revelation
   - Shot 5 (00:08 - 00:10): Hero resolve / iconic hold into the final frame
5. NO ON-SCREEN TEXT OR SUBTITLES:
   The video stream must contain no rendered text, logos, or subtitles.
6. THREE DISTINCT BALANCED STYLES PER SCENARIO:
   For each scenario, provide 3 switchable 'styles' variations of the exact same 5 narrative actions:
   - Style 1: Signature Vision (the bold, stylized aesthetic matching the scenario's primary creative genre)
   - Style 2: Clean Modern Tech / Studio Commercial ("Попроще" / Grounded Realism — sleek, approachable, high-end commercial or modern studio look with clean lighting, natural skin tones, professional elegance, avoiding surreal fantasy)
   - Style 3: Dynamic Cinematic Realism / Contrasting Movement (distinct cinematic color grade, lens, and pacing)
   Give each style an evocative, descriptive name (do NOT name them "Style 1" or "Style 2").
7. OMNI PROMPT:
   Include a complete multi-shot prompt explicitly listing all 5 shots with timestamps (00:00 - 00:02, 00:02 - 00:04, 00:04 - 00:06, 00:06 - 00:08, 00:08 - 00:10).
8. ANONYMOUS PROTAGONIST DIRECTIVE (CRITICAL PRIVACY RULE):
   NEVER write, mention, or output the speaker's real personal name in any shot descriptions, actions, camera notes, lighting atmosphere, concepts, or omni prompts.
   ALWAYS refer to the character as "the protagonist" or "the hero" (or pronouns like 'she' / 'he').
   The actor's physical likeness is supplied visually through the uploaded reference photo, NOT by name in text prompts.
"""


def _build_single_scenario_from_genre(
    g: GenreBrief,
    idx: int,
    talk_title: str,
    speaker_name: str,
) -> CreativeScenario:
    """Builds a single structured 5-shot scenario directly from a GenreBrief."""
    shots = [
        VideoShot(
            shot_number=1,
            time_range="00:00 - 00:02",
            action=f"The protagonist enters the world of {g.genre}, taking in the surroundings of {g.visual_universe.split('.')[0]}.",
            camera="Atmospheric wide establishing shot pushing slowly forward.",
            lighting_atmosphere=f"Signature {g.aesthetic_manifesto.split('.')[0]}.",
        ),
        VideoShot(
            shot_number=2,
            time_range="00:02 - 00:04",
            action=f"The protagonist initiates a pivotal interaction, setting {g.narrative_metaphor.lower()} in motion.",
            camera="Dynamic tracking shot following the rapid movement.",
            lighting_atmosphere="Deep cinematic shadows with sharp directional highlights.",
        ),
        VideoShot(
            shot_number=3,
            time_range="00:04 - 00:06",
            action="At the center of the space, the protagonist maneuvers complex physical components representing the core mechanism.",
            camera="Intense low-angle rotational close-up.",
            lighting_atmosphere="Vibrant specular reflections and rich atmospheric depth.",
        ),
        VideoShot(
            shot_number=4,
            time_range="00:06 - 00:08",
            action="The environment responds to the protagonist's action, revealing a breathtaking transformation of the entire space.",
            camera="Expansive crane tilt-up revealing the wider visual architecture.",
            lighting_atmosphere="Volumetric shafts of light cutting across the scene.",
        ),
        VideoShot(
            shot_number=5,
            time_range="00:08 - 00:10",
            action="The protagonist holds an iconic, confident stance amidst the transformed world as the final frame locks in.",
            camera="Dramatic centered hero hold into the final frame.",
            lighting_atmosphere="Stunning golden-hour rim lighting with crisp silhouette.",
        ),
    ]
    sc = CreativeScenario(
        id=g.id or f"scenario_{idx}",
        title=g.title,
        genre=g.genre,
        concept=f"{g.visual_universe} {g.narrative_metaphor}",
        narrative_metaphor=g.narrative_metaphor,
        shots=shots,
        omni_prompt=format_timed_omni_prompt(shots, g.genre),
        number=idx,
    )
    _ensure_scenario_styles(sc, idx)
    return sc


def _build_scenarios_from_genres(
    genres: list[GenreBrief],
    talk_title: str,
    speaker_name: str,
) -> list[CreativeScenario]:
    """Generates structural 5-shot scenarios directly from GenreBrief objects."""
    return [
        _build_single_scenario_from_genre(g, idx, talk_title, speaker_name) for idx, g in enumerate(genres, start=1)
    ]


def direct_single_scenario(
    genre: GenreBrief,
    idx: int,
    talk_title: str,
    speaker_name: str,
    position_company: str | None = None,
    speaker_bio: str | None = None,
    creative_guidance: str | None = None,
    temperature: float = 1.5,
) -> CreativeScenario:
    """Directs a single 5-shot cinematic storyboard for one assigned genre concept with high temperature (1.5)."""
    client = get_gemini_client()

    context_lines = [
        f"Talk Title: {talk_title}",
        "Protagonist / Hero: The protagonist (ANONYMOUS: NEVER output or use real personal names in shot actions, cameras, or prompts)",
    ]
    if position_company:
        context_lines.append(f"Domain / Focus: {position_company}")
    if speaker_bio:
        context_lines.append(f"Speaker Background / Expertise: {speaker_bio}")

    user_prompt = (
        f"Direct a 5-shot x 2-second cinematic storyboard for Option {idx}.\n\n"
        f"CONTEXT:\n" + "\n".join(context_lines) + "\n\n"
        f"ASSIGNED GENRE BRIEF:\n"
        f"- Identifier: {genre.id}\n"
        f"- Title: {genre.title}\n"
        f"- Genre / Universe: {genre.genre}\n"
        f"- Visual Universe: {genre.visual_universe}\n"
        f"- Aesthetic Manifesto: {genre.aesthetic_manifesto}\n"
        f"- Narrative Metaphor to Dramatize: {genre.narrative_metaphor}\n\n"
        "MANDATORY REQUIREMENTS:\n"
        "- Protagonist is the main character and hero of this mini-film.\n"
        "- ABSOLUTELY NO REAL NAMES: NEVER write the speaker's personal name in shot descriptions, actions, camera notes, lighting atmosphere, or omni prompts. Always use 'the protagonist' or 'the hero'.\n"
        "- Strictly NO public speaking, conference halls, stage, audience, or slides.\n"
        "- FAITHFULLY IMPLEMENT THE ASSIGNED GENRE: The shots, atmosphere, and camera movements must match the assigned aesthetic manifesto and visual universe.\n"
        "- Exactly 5 progressive shots of 2 seconds each (total 10 seconds).\n"
        "- 'concept': A vivid 2-sentence storyline plot synopsis describing what happens to the protagonist across these 5 shots in this mini-film.\n"
        "- Provide 3 switchable 'styles' variations with UNIQUE names tailored specifically to this world and story (NEVER reuse generic labels like 'Clean Modern Tech' across options):\n"
        "  * Style 1: Primary Aesthetic (the core bold signature aesthetic of this world)\n"
        "  * Style 2: Grounded / Commercial Alternative ('Попроще' - clean studio/natural commercial lighting and elegant realism, tailored to this universe)\n"
        "  * Style 3: Radical / Contrasting Movement (high-contrast, distinct lens, kinetic camera, or moody color grade tailored to this universe)\n"
        "- 'shots': A list of exactly 5 shot objects, each with 'shot_number' (1..5), 'time_range' ('00:00 - 00:02', '00:02 - 00:04', etc.), 'action', 'camera', and 'lighting_atmosphere'.\n"
        "- 'omni_prompt' MUST explicitly incorporate all 5 shots with their exact timestamps (00:00 - 00:02, 00:02 - 00:04, 00:04 - 00:06, 00:06 - 00:08, 00:08 - 00:10).\n"
        "- Deliver a JSON object containing: 'id', 'title', 'genre', 'concept', 'narrative_metaphor', 'shots' (5 shot objects), 'styles' (3 styles), and 'omni_prompt'."
    )

    retries = 3
    delay = 2.0
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=PROMPT_DIRECTOR_MODEL,
                contents=[types.Part.from_text(text=user_prompt)],
                config=types.GenerateContentConfig(
                    system_instruction=SHOT_DIRECTOR_INSTRUCTION,
                    temperature=temperature,
                    top_p=1.0,
                    response_mime_type="application/json",
                ),
            )
            raw_entry: Any = None
            if response.parsed:
                if getattr(response.parsed, "scenarios", None) and response.parsed.scenarios:
                    raw_entry = response.parsed.scenarios[0]
                elif getattr(response.parsed, "id", None) or getattr(response.parsed, "title", None):
                    raw_entry = response.parsed
            elif response.text:
                cleaned_json = response.text.strip()
                if cleaned_json.startswith("```"):
                    cleaned_json = re.sub(r"^```(?:json)?\n?", "", cleaned_json)
                    cleaned_json = re.sub(r"\n?```$", "", cleaned_json).strip()
                data = json.loads(cleaned_json)
                if isinstance(data, dict):
                    if "scenarios" in data and isinstance(data["scenarios"], list) and data["scenarios"]:
                        raw_entry = data["scenarios"][0]
                    else:
                        raw_entry = data
                elif isinstance(data, list) and data:
                    raw_entry = data[0]

            if raw_entry:
                sc = _normalize_scenario_item(raw_entry, idx, speaker_name=speaker_name)
                if sc:
                    if not sc.genre or sc.genre == "Cinematic / Commercial":
                        sc.genre = genre.genre
                    if not sc.title or sc.title == f"Scenario {idx}":
                        sc.title = genre.title
                    if not sc.narrative_metaphor:
                        sc.narrative_metaphor = genre.narrative_metaphor
                    if not sc.concept or sc.concept.strip() in (
                        "A high-concept visual story.",
                        "A high-concept visual story",
                    ):
                        if sc.shots and len(sc.shots) >= 3:
                            sc.concept = f"{genre.title}: {sc.shots[0].action} The narrative escalates into {sc.shots[3].action.lower()}."
                        elif genre.narrative_metaphor:
                            sc.concept = f"Set in {genre.visual_universe}, {genre.narrative_metaphor.lower()}."
                    sc.number = idx
                    _ensure_scenario_styles(sc, idx)
                    return sc
            break
        except Exception as e:
            err_str = str(e).lower()
            is_transient = any(
                marker in err_str
                for marker in ("429", "resource_exhausted", "too many requests", "quota", "503", "unavailable")
            )
            if attempt < retries - 1 and is_transient:
                time.sleep(delay)
                delay *= 2.0
                continue
            print(f"⚠️ [Parallel Shot Director] Worker for '{genre.title}' failed: {e}")
            break

    return _build_single_scenario_from_genre(genre, idx, talk_title, speaker_name)


def direct_scenarios_from_genres(
    genres: list[GenreBrief],
    talk_title: str,
    speaker_name: str,
    position_company: str | None = None,
    speaker_bio: str | None = None,
    temperature: float = 1.5,
) -> list[CreativeScenario]:
    """Stage 2: Directs each pre-selected creative genre via concurrent sub-directors (throttled to 2 workers to prevent 429 quota bursts)."""
    if not genres:
        return []

    max_workers = min(len(genres), 2)
    results: list[tuple[int, CreativeScenario]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {}
        for i, g in enumerate(genres, start=1):
            future = executor.submit(
                direct_single_scenario,
                genre=g,
                idx=i,
                talk_title=talk_title,
                speaker_name=speaker_name,
                position_company=position_company,
                speaker_bio=speaker_bio,
                temperature=temperature,
            )
            future_to_idx[future] = i
            # Gentle stagger between thread dispatches to prevent 429 quota burst
            if i < len(genres):
                time.sleep(0.35)

        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                sc = future.result()
                results.append((idx, sc))
            except Exception as e:
                print(f"⚠️ [Parallel Shot Director] Execution failed for genre index {idx}: {e}")
                results.append((idx, _build_single_scenario_from_genre(genres[idx - 1], idx, talk_title, speaker_name)))

    results.sort(key=lambda x: x[0])
    final_scenarios = [r[1] for r in results]
    print(
        f"🎬 [Shot Director] Successfully directed {len(final_scenarios)} 5-shot scenarios concurrently via Gemini ({PROMPT_DIRECTOR_MODEL})"
    )
    return final_scenarios


def reorder_shots_and_rebuild_prompt(
    shots: Sequence[VideoShot | dict[str, Any]],
    genre: str = "",
) -> tuple[list[VideoShot], str]:
    """Re-indexes an arbitrarily ordered sequence of shots to 2-second intervals (1..5) and rebuilds the timed omni prompt."""
    reindexed_shots: list[VideoShot] = []
    for i, raw_sh in enumerate(shots, start=1):
        if isinstance(raw_sh, VideoShot):
            action = raw_sh.action
            camera = raw_sh.camera
            lighting = raw_sh.lighting_atmosphere
        elif isinstance(raw_sh, dict):
            action = raw_sh.get("action", "")
            camera = raw_sh.get("camera", "")
            lighting = raw_sh.get("lighting_atmosphere", raw_sh.get("lightingAtmosphere", ""))
        else:
            action = getattr(raw_sh, "action", "")
            camera = getattr(raw_sh, "camera", "")
            lighting = getattr(raw_sh, "lighting_atmosphere", "")

        start_sec = (i - 1) * 2
        end_sec = i * 2
        time_range = f"00:0{start_sec} - 00:{end_sec:02d}"
        reindexed_shots.append(
            VideoShot(
                shot_number=i,
                time_range=time_range,
                action=str(action).strip(),
                camera=str(camera).strip(),
                lighting_atmosphere=str(lighting).strip(),
            )
        )
    prompt = format_timed_omni_prompt(reindexed_shots, genre=genre)
    return reindexed_shots, prompt


def generate_creative_scenarios(
    talk_title: str,
    speaker_name: str,
    position_company: str | None = None,
    speaker_bio: str | None = None,
    creative_guidance: str | None = None,
    count: int = 5,
    genres: Sequence[GenreBrief] | None = None,
) -> list[CreativeScenario]:
    """Two-Stage Creative Pipeline:
    Stage 1: Scout radically diverse creative genres and visual universes (high stochasticity & entropy).
    Stage 2: Direct 5-shot x 2-second storyboards and styles for each scouted genre.
    """
    # Stage 1: Scout creative genres if not supplied
    if not genres:
        genres = scout_creative_genres(
            talk_title=talk_title,
            speaker_name=speaker_name,
            position_company=position_company,
            speaker_bio=speaker_bio,
            creative_guidance=creative_guidance,
            count=count,
        )

    # Stage 2: Direct shots and styles for the selected genres
    return direct_scenarios_from_genres(
        genres=list(genres),
        talk_title=talk_title,
        speaker_name=speaker_name,
        position_company=position_company,
        speaker_bio=speaker_bio,
    )


def format_scenarios_markdown(scenarios: Sequence[CreativeScenario]) -> str:
    """Formats scenarios into human-friendly Markdown for user preview and chat display."""
    lines = [
        "### 🎬 Creative Video Scenarios (5 shots × 2s each)",
        "Choose **one** scenario from the options below to proceed with rendering, or feel free to edit it or request new concepts.",
        "",
    ]
    for idx, sc in enumerate(scenarios, start=1):
        _ensure_scenario_styles(sc, idx)
        lines.append(f"#### Option {idx}: {sc.title} (`{sc.genre}`)")
        lines.append(f"**Concept:** {sc.concept}\n")
        if sc.narrative_metaphor:
            lines.append(f"**Metaphor & Story Bridge:** {sc.narrative_metaphor}\n")
        lines.append("| Shot | Timing | Action & Atmosphere | Camera Dynamic |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for sh in sc.shots:
            lines.append(
                f"| **Shot {sh.shot_number}** | `{sh.time_range}` | {sh.action} *({sh.lighting_atmosphere})* | {sh.camera} |"
            )
        lines.append("")
        lines.append(f"> **Omni Prompt ({sc.id}):**\n> {sc.omni_prompt}\n")
        if sc.styles:
            styles_json = json.dumps([st.model_dump() for st in sc.styles])
            lines.append(f"<!-- SCENARIO_STYLES_JSON:{styles_json} -->\n")
    return "\n".join(lines)
