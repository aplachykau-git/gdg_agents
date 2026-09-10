from __future__ import annotations

import json
import os
import re
from typing import Any, Sequence

from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

from agents.gemini_config import get_gemini_client

from .workflow_models import CreativeScenario, ScenarioStyle, VideoShot

PROMPT_DIRECTOR_MODEL = os.getenv("VIDEO_PROMPT_DIRECTOR_MODEL", "gemini-3.5-flash")

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
Your task is to transform a speaker's talk topic, title, and bio into 3 wildly imaginative narrative video scenarios with completely contrasting aesthetics and vibes.
For EACH of the 3 scenarios, you will also provide 3 switchable stylistic aesthetics (so 3 narrative storylines x 3 styles = 9 total visual styles).

CRITICAL RULES:
1. PROTAGONIST: The person from the portrait photo is the hero/protagonist of the mini-film. Do NOT critique, analyze, or evaluate their facial features, clothing, or the original background of the photo.
2. ABSOLUTELY NO PUBLIC SPEAKING: Strictly avoid any conference stages, presentation podiums, lecture halls, audiences, microphones, slide decks, or classroom settings.
3. VAST TONAL DIVERSITY ACROSS SCENARIOS (AVOID ALL-SCI-FI REPETITION & STATIC TROPES):
   The 3 options MUST NEVER share the same genre or mood. You MUST deliver 3 completely contrasting creative worlds and advertising vibes.
   Freely explore a wide spectrum of creative genres and visual tones tailored to the topic and any user direction:
   - High-Energy Kinetic Commercial / Brand Launch (Nike / Apple Keynote / athletic adrenaline / urban whip-pans)
   - Stylized Pop-Art / Whimsical Editorial (Wes Anderson / Vogue / symmetrical color-blocking / quirky tactile physics)
   - Retro-Analog 70s/80s Espionage / Cinema (Kodak 35mm / golden grain / tactile mechanical dials / warm nostalgia)
   - Solarpunk Architectural Daylight (lush bioluminescent botanicals / sun-drenched glass / clean optimism)
   - Atmospheric Neo-Noir / Mystery Thriller (rain-slicked obsidian / cyan fiber-optics / dramatic shadow silhouettes)
   - Minimalist Luxury / High-Fashion Fragrance (sculptural brutalism / fluid silk / avant-garde lighting)
   - Kinetic Anime / Manga Metaphor (electric aura / dynamic speed lines / hyper-stylized motion)
4. METAPHORICAL CONNECTION: Creatively translate the abstract themes of the talk (e.g., distributed data, neural networks, security, speed, resilience, debugging) into thrilling, memorable visual metaphors.
5. 5 SHOTS x 2 SECONDS (EXACTLY 10 SECONDS TOTAL): Each scenario must consist of exactly 5 sequential shots, exactly 2 seconds each:
   - Shot 1 (00:00 - 00:02): Hook / Entrance into the world
   - Shot 2 (00:02 - 00:04): Dynamic escalation / visual metaphor in motion
   - Shot 3 (00:04 - 00:06): Intense action / peak interaction of the protagonist
   - Shot 4 (00:06 - 00:08): Dramatic climax / revelation
   - Shot 5 (00:08 - 00:10): Hero resolve / iconic hold into the final frame
6. NO ON-SCREEN TEXT OR SUBTITLES: Video will have graphics composited separately. The visual video stream must contain no rendered text, logos, or subtitles.
7. STYLES PER SCENARIO (PRESERVE SHOT ACTIONS, VARY VISUAL AESTHETICS):
   For each scenario, define the core narrative plot (concept) with its 5 shots.
   Then provide 3 switchable 'styles' variations of this exact plot.
   CRITICAL REQUIREMENT: The 5 shots MUST retain their core narrative actions (what the protagonist does remains the same storyline across all 3 styles), BUT each style dramatically re-envisions the visual atmosphere, camera lenses, color grade, and omni_prompt.
   Example styles for a scenario:
     - Style 1: Signature Look (matching the scenario's primary genre)
     - Style 2: Contrasting Aesthetic A (e.g. "Pastel Pop-Art" or "Cyber-Noir Neon" or "Solarpunk Daylight")
     - Style 3: Contrasting Aesthetic B (e.g. "Warm 35mm Analog" or "High-Gloss Studio Ad" or "Monochrome Noir")
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
    shots: list[Any] = Field(default_factory=list, description="5 progressive shots detailing the 10-second sequence")
    omni_prompt: str | None = Field(default=None, alias="omniPrompt", description="Complete 9:16 multi-shot prompt")
    styles: list[Any] = Field(default_factory=list, description="Switchable styles for the scenario")


class _RawGeneratedScenarios(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scenarios: list[Any] = Field(default_factory=list)


def _normalize_shot(raw: Any, idx: int) -> VideoShot:
    """Safely convert dict/object/string into a validated VideoShot with defaults."""
    if isinstance(raw, VideoShot):
        return raw

    default_timing = DEFAULT_TIMINGS[min(idx - 1, len(DEFAULT_TIMINGS) - 1)]
    if isinstance(raw, str):
        return VideoShot(
            shot_number=idx,
            time_range=default_timing,
            action=_sanitize_scenario_text(raw),
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
            or f"Protagonist drives the action in shot {idx}."
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
            action=_sanitize_scenario_text(action),
            camera=_sanitize_scenario_text(camera),
            lighting_atmosphere=_sanitize_scenario_text(lighting),
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
        or f"Protagonist drives the action in shot {idx}."
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
        action=_sanitize_scenario_text(action),
        camera=_sanitize_scenario_text(camera),
        lighting_atmosphere=_sanitize_scenario_text(lighting),
    )


def _normalize_scenario_item(entry: Any, idx: int) -> CreativeScenario | None:
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
    concept = _sanitize_scenario_text(str(entry.get("concept") or "A high-concept visual story."))

    # Extract shots: prefer entry["shots"], else fallback to entry["styles"][0]["shots"]
    raw_shots = entry.get("shots") or []
    raw_styles = entry.get("styles") or []

    if not raw_shots and raw_styles and isinstance(raw_styles, list):
        first_style = raw_styles[0]
        if isinstance(first_style, dict):
            raw_shots = first_style.get("shots", [])
        elif hasattr(first_style, "shots"):
            raw_shots = getattr(first_style, "shots", [])

    shots = [_normalize_shot(sh, s_idx) for s_idx, sh in enumerate(raw_shots, start=1)]

    # If shots are missing or fewer than 5, fill progressive shots
    while len(shots) < 5:
        s_idx = len(shots) + 1
        shots.append(
            VideoShot(
                shot_number=s_idx,
                time_range=DEFAULT_TIMINGS[min(s_idx - 1, len(DEFAULT_TIMINGS) - 1)],
                action=f"The protagonist drives the visual climax in phase {s_idx} with commanding presence.",
                camera="Dynamic cinematic camera move with dramatic depth of field.",
                lighting_atmosphere="Rich volumetric lighting and cinematic atmosphere.",
            )
        )

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
        omni_prompt = _sanitize_scenario_text(omni_prompt)

    # Process styles if provided
    styles: list[ScenarioStyle] = []
    if raw_styles and isinstance(raw_styles, list):
        for st_idx, st_raw in enumerate(raw_styles, start=1):
            if isinstance(st_raw, dict):
                st_id = str(st_raw.get("id") or f"{sc_id}_style_{st_idx}")
                st_name = str(st_raw.get("name") or f"Style {st_idx}")
                st_genre = str(st_raw.get("genre") or genre)
                st_shots_raw = st_raw.get("shots") or shots
                st_shots = [_normalize_shot(sh, sh_idx) for sh_idx, sh in enumerate(st_shots_raw, start=1)]
                st_prompt = str(st_raw.get("omni_prompt") or st_raw.get("omniPrompt") or "")
                if not any(marker in st_prompt.lower() for marker in ("00:00", "0-2s", "shot 1", "shot 2")):
                    st_prompt = format_timed_omni_prompt(st_shots, st_genre, st_prompt)
                styles.append(
                    ScenarioStyle(id=st_id, name=st_name, genre=st_genre, shots=st_shots, omni_prompt=st_prompt)
                )
            elif isinstance(st_raw, str):
                st_id = f"{sc_id}_style_{st_idx}"
                st_name = st_raw
                st_genre = st_raw
                st_shots = list(shots)
                st_prompt = format_timed_omni_prompt(st_shots, st_genre)
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
        shots=shots,
        omni_prompt=omni_prompt,
        styles=styles,
    )
    return _ensure_scenario_styles(sc)


def _sanitize_scenario_text(text: str) -> str:
    """Ensure no conference/stage terms seep through."""
    cleaned = text
    for term in FORBIDDEN_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "cinematic space", cleaned, flags=re.IGNORECASE)
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
    """Deterministic fallback scenarios providing 3 completely contrasting commercial and cinematic vibes."""
    base_title = talk_title or "Future Technology"
    return [
        CreativeScenario(
            id="scenario_kinetic_commercial",
            title="The Velocity Catalyst",
            genre="High-Energy Kinetic Commercial / Brand Launch",
            concept=f"A fast-paced kinetic commercial visualizing the explosive performance and instant response of '{base_title}' through urban athletic motion, sleek chrome reflections, and dynamic lighting.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist sprints across a sleek architectural glass bridge as glowing pulse ribbons race alongside them.",
                    camera="Low-angle tracking sprint, rapid kinetic motion blur.",
                    lighting_atmosphere="Electric cyan and crisp white LED reflections on glass.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="They execute a sharp dynamic leap over a suspended threshold, catching floating luminous particles in mid-air.",
                    camera="120fps ultra-slow-motion floating camera arc.",
                    lighting_atmosphere="Radiant amber rim-lighting with specular flares.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="Mid-air, they snap a polished metallic core into place, triggering a massive shockwave of light.",
                    camera="Dynamic crash-zoom into the locking mechanism.",
                    lighting_atmosphere="High-contrast strobe pulse of magenta and electric gold.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="The shockwave illuminates an expansive metropolis grid humming at peak speed below.",
                    camera="Sweeping bird's-eye dive down into the illuminated urban canyon.",
                    lighting_atmosphere="Vibrant multi-spectrum neon grid glow.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="Protagonist lands with effortless balance, looking up with calm, commanding confidence as the city breathes in sync behind them.",
                    camera="Centered hero push-in with confident cinematic hold.",
                    lighting_atmosphere="Sleek high-fashion twilight with crisp edge highlights.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 high-energy kinetic brand commercial. "
                "Shot 1 (00:00 - 00:02): Low-angle tracking sprint across a glass bridge with racing cyan neon ribbons. "
                "Shot 2 (00:02 - 00:04): 120fps slow-motion leap catching floating amber particles in mid-air. "
                "Shot 3 (00:04 - 00:06): Crash-zoom into locking a polished metallic core triggering a vibrant strobe pulse. "
                "Shot 4 (00:06 - 00:08): Bird's-eye dive down illuminating an expansive high-speed cyber-metropolis. "
                "Shot 5 (00:08 - 00:10): Centered hero landing and confident hold against sleek twilight skyline."
            ),
        ),
        CreativeScenario(
            id="scenario_pop_art",
            title="Pastel Precision & The Quirky Engine",
            genre="Stylized Pop-Art / Wes Anderson Commercial",
            concept=f"A delightfully quirky, symmetrical pop-art commercial where complex principles of '{base_title}' are orchestrated through tactile pastel mechanical modules, brass gears, and whimsical precision.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist in a sharply tailored retro suit sits at a perfectly symmetrical pastel-mint console with brass dials.",
                    camera="Dead-center symmetrical wide framing, crisp snap-in.",
                    lighting_atmosphere="Soft, shadowless editorial pastel lighting in mint and coral.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="They flick a bright yellow toggle switch; an intricate domino line of pastel wooden blocks begins tumbling in rhythm.",
                    camera="Rapid 90-degree whip-pan following the mechanical cascade.",
                    lighting_atmosphere="Sun-drenched warm retro interior glow.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="Protagonist calmly adjusts vintage glasses as a miniature brass bell dings and releases a floating origami cloud.",
                    camera="Extreme close-up on their eyes, then witty rack-focus to the origami.",
                    lighting_atmosphere="Soft morning daylight with crisp geometric shadows.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="The whimsical contraption pours a perfect droplet of glowing blue liquid into a tiny porcelain teacup.",
                    camera="Overhead top-down flat-lay tracking the falling droplet in slow-motion.",
                    lighting_atmosphere="High-gloss studio commercial illumination.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="Protagonist takes a calm sip from the teacup, giving a knowing, witty glance directly into the lens as the machine purrs harmoniously.",
                    camera="Centered medium hero framing, subtle slow push.",
                    lighting_atmosphere="Radiant pastel warmth with retro Kodak color saturation.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 stylized pop-art Wes Anderson commercial. "
                "Shot 1 (00:00 - 00:02): Symmetrical wide framing of protagonist at a pastel-mint console with brass dials. "
                "Shot 2 (00:02 - 00:04): Snappy 90-degree whip-pan following a cascading domino run of pastel blocks. "
                "Shot 3 (00:04 - 00:06): Extreme close-up with witty rack-focus to a floating origami cloud. "
                "Shot 4 (00:06 - 00:08): Overhead top-down shot of a droplet falling into a tiny porcelain teacup. "
                "Shot 5 (00:08 - 00:10): Centered hero sipping tea with a knowing glance into camera, radiant pastel warmth."
            ),
        ),
        CreativeScenario(
            id="scenario_epic_noir",
            title="Midnight Obsidian Protocol",
            genre="Atmospheric Cinematic Thriller / Neo-Noir",
            concept=f"A moody cinematic thriller following the protagonist untangling hidden anomalies in '{base_title}' amidst rain-drenched streets, flickering neon signs, and deep atmospheric suspense.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist walks through a rain-drenched alley, reflected in oil-slick puddles under buzzing amber streetlamps.",
                    camera="Low-angle slow glide through rising steam and raindrops.",
                    lighting_atmosphere="Deep chiaroscuro shadows with warm sodium-vapor glow.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="They pull open a heavy rusted metal hatch, revealing a cavernous data vault glowing with thousands of cold fiber-optic fibers.",
                    camera="Dolly-in over their shoulder into the cavernous darkness.",
                    lighting_atmosphere="Striking contrast of pitch-black shadows and electric cyan filament glow.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="Protagonist reaches into a humming pool of dark liquid glass, extracting a crystalline prism that refracts blinding white beams.",
                    camera="Close-up rotational tracking around the glowing crystal prism.",
                    lighting_atmosphere="Blinding specular god-rays piercing through the mist.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="The room stabilizes as the discordant hum harmonizes into a deep, soothing acoustic resonance.",
                    camera="Expansive crane tilt-up revealing monumental concrete brutalist architecture.",
                    lighting_atmosphere="Volumetric shafts of cold moonlight cutting through rain haze.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="Protagonist stands atop monumental steps, holding the quiet crystal as dawn breaks over the rain-washed skyline.",
                    camera="Dramatic centered hero hold into the final frame.",
                    lighting_atmosphere="Golden-hour rim light catching rain droplets on their collar.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 atmospheric neo-noir thriller. "
                "Shot 1 (00:00 - 00:02): Low-angle slow glide following protagonist through a rain-slicked alley with amber streetlamps. "
                "Shot 2 (00:02 - 00:04): Dolly-in over shoulder into a cavernous vault glowing with cold cyan fiber-optics. "
                "Shot 3 (00:04 - 00:06): Rotational close-up extracting a glowing crystal prism with blinding specular god-rays. "
                "Shot 4 (00:06 - 00:08): Expansive crane tilt-up across brutalist concrete architecture in volumetric moonlight. "
                "Shot 5 (00:08 - 00:10): Heroic hold on monumental steps holding the crystal at dawn, golden rim-lighting."
            ),
        ),
    ]


def _ensure_scenario_styles(sc: CreativeScenario) -> CreativeScenario:
    """Ensure every scenario has 3 switchable style tabs adapting the same narrative plot."""
    if sc.styles and len(sc.styles) >= 3:
        if not sc.shots and sc.styles[0].shots:
            sc.shots = sc.styles[0].shots
        if not sc.omni_prompt and sc.styles[0].omni_prompt:
            sc.omni_prompt = sc.styles[0].omni_prompt
        if not sc.genre and sc.styles[0].genre:
            sc.genre = sc.styles[0].genre
        return sc

    base_genre = sc.genre or "Cinematic Film"
    base_lower = base_genre.lower()

    # Style 1: Signature
    style1_name = sc.genre.split("/")[0].strip() if "/" in sc.genre else sc.genre
    style1 = ScenarioStyle(
        id=f"{sc.id}_style_1",
        name=style1_name or "Style 1 (Signature)",
        genre=sc.genre,
        shots=list(sc.shots),
        omni_prompt=sc.omni_prompt,
    )

    # Rich library of style presets for high visual variety
    style_presets = [
        {
            "name": "High-Gloss Studio Ad",
            "genre": "High-Gloss Studio Commercial / Luxury Editorial",
            "camera": "Silky crane movement, seamless rotational studio tracking, macro product-reveal elegance.",
            "lighting": "Pristine white studio rim-lighting with soft diffused champagne reflections.",
            "tags": ["gloss", "commercial", "luxury", "studio", "clean"],
        },
        {
            "name": "Pastel Pop-Art",
            "genre": "Stylized Pop-Art / Symmetrical Commercial",
            "camera": "Snappy 90-degree whip-pan, dead-center symmetrical framing, rapid playful snap-in.",
            "lighting": "Shadowless pastel mint and coral lighting with vivid retro saturation.",
            "tags": ["pop", "wes anderson", "pastel", "quirky", "symmetrical"],
        },
        {
            "name": "Warm 35mm Film",
            "genre": "Warm 35mm Analog / Kodak Cinema",
            "camera": "Tactile handheld 35mm camera, organic camera breathing, shallow prime lens focus.",
            "lighting": "Warm golden tungsten lamps, soft film halation, tactile organic film grain.",
            "tags": ["film", "analog", "vintage", "warm", "35mm", "retro"],
        },
        {
            "name": "Cyber-Neon Noir",
            "genre": "Atmospheric Cyber-Neon / Sci-Fi Noir",
            "camera": "Low-angle kinetic tracking, rapid anamorphic push-in, reflective puddle sweeps.",
            "lighting": "Deep obsidian shadows punctuated by electric cyan and magenta neon strobes.",
            "tags": ["cyber", "neon", "noir", "matrix", "dark", "sci-fi"],
        },
        {
            "name": "Solarpunk Daylight",
            "genre": "Solarpunk / Architectural Daylight",
            "camera": "Silky Steadicam glide, elegant shallow depth of field, wide natural framing.",
            "lighting": "Bright natural sunlight, shimmering dust motes, clean architectural reflections.",
            "tags": ["solar", "daylight", "bright", "architecture", "nature", "green"],
        },
        {
            "name": "Monochrome Noir",
            "genre": "High-Contrast Monochrome Noir / Arthouse",
            "camera": "Steep Dutch angle, vintage silver-halide prime lens, dramatic close profile.",
            "lighting": "Chiaroscuro black-and-white lighting, deep shadow silhouettes, intense directional beams.",
            "tags": ["monochrome", "noir", "black and white", "arthouse", "contrast"],
        },
    ]

    # Pick 2 style presets that contrast most strongly with the base genre
    chosen_presets = []
    for preset in style_presets:
        if not any(tag in base_lower for tag in preset["tags"]):
            chosen_presets.append(preset)
            if len(chosen_presets) == 2:
                break

    if len(chosen_presets) < 2:
        for preset in style_presets:
            if preset not in chosen_presets:
                chosen_presets.append(preset)
                if len(chosen_presets) == 2:
                    break

    p2, p3 = chosen_presets[0], chosen_presets[1]

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


def generate_creative_scenarios(
    talk_title: str,
    speaker_name: str,
    position_company: str | None = None,
    speaker_bio: str | None = None,
    creative_guidance: str | None = None,
    count: int = 3,
) -> list[CreativeScenario]:
    """Generates 3 wildly creative 5-shot x 2-second video scenarios using gemini-3.5-flash on the fly.
    The person from the photo is the hero. Absolutely NO public speaking or conference settings.
    """
    client = get_gemini_client()
    context_lines = [
        f"Talk Title: {talk_title}",
        f"Speaker / Protagonist Name: {speaker_name}",
    ]
    if position_company:
        context_lines.append(f"Domain / Focus: {position_company}")
    if speaker_bio:
        context_lines.append(f"Speaker Background / Expertise: {speaker_bio}")
    if creative_guidance:
        context_lines.append(f"User Requested Creative Tone & Vibe Direction: {creative_guidance}")

    guidance_instruction = ""
    if creative_guidance:
        guidance_instruction = (
            f"\nSPECIAL USER CREATIVE DIRECTION: The user explicitly requested: '{creative_guidance}'. "
            "Please heavily incorporate this mood, aesthetic, tone, or style into the scenario concepts!\n"
        )

    user_prompt = (
        f"Please invent {count} wildly different, highly creative, UNEXPECTED video scenarios for this protagonist and topic, inspired by high-end commercials, brand teasers, luxury campaigns, music videos, and stylized cinema.\n"
        f"CONTEXT:\n" + "\n".join(context_lines) + "\n"
        f"{guidance_instruction}\n"
        "MANDATORY REQUIREMENTS:\n"
        "- Protagonist is the main character and hero of each mini-film.\n"
        "- ABSOLUTELY NO public speaking, NO conference halls, NO stage, NO audience, NO slides.\n"
        "- RADICAL TONAL & GENRE DIVERSITY ACROSS SCENARIOS:\n"
        "  * Each scenario MUST explore a completely distinct visual genre, atmosphere, and pacing.\n"
        "  * Avoid repeating the same concepts or aesthetic tropes across options.\n"
        "  * Freely explore diverse creative worlds: e.g. sleek hyper-kinetic sportswear ad, high-fashion surrealist editorial, retro-analog 70s espionage thriller, cyberpunk neon heist, sun-drenched architectural solarpunk, whimsical stop-motion pop art, moody sci-fi expedition, or bold typographic motion-design commercial.\n"
        "- Translate abstract themes into memorable, exciting visual metaphors.\n"
        "- Exactly 5 progressive shots of 2 seconds each (total 10 seconds).\n"
        "- For EACH scenario, provide 3 switchable 'styles' (Style 1: Signature look matching genre; Style 2 & 3: contrasting visual aesthetics adapting the same narrative actions with different lighting, camera, and color grade).\n"
        "- 'omni_prompt' MUST explicitly incorporate all 5 shots with their exact time stamps (00:00 - 00:02, 00:02 - 00:04, 00:04 - 00:06, 00:06 - 00:08, 00:08 - 00:10).\n"
        "- Deliver a JSON object with 'scenarios' list containing id, title, concept, genre, shots, omni_prompt, and styles."
    )

    try:
        response = client.models.generate_content(
            model=PROMPT_DIRECTOR_MODEL,
            contents=[types.Part.from_text(text=user_prompt)],
            config=types.GenerateContentConfig(
                system_instruction=PROMPT_DIRECTOR_INSTRUCTION,
                temperature=1.35,
                top_p=0.95,
                response_mime_type="application/json",
            ),
        )
        raw_list: list[Any] = []
        if response.parsed and getattr(response.parsed, "scenarios", None):
            raw_list = response.parsed.scenarios
        elif response.text:
            cleaned_json = response.text.strip()
            if cleaned_json.startswith("```"):
                cleaned_json = re.sub(r"^```(?:json)?\n?", "", cleaned_json)
                cleaned_json = re.sub(r"\n?```$", "", cleaned_json).strip()
            data = json.loads(cleaned_json)
            raw_list = data.get("scenarios", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

        final_scenarios: list[CreativeScenario] = []
        for idx, entry in enumerate(raw_list, start=1):
            sc = _normalize_scenario_item(entry, idx)
            if sc:
                final_scenarios.append(sc)

        if final_scenarios:
            print(
                f"🎬 [Prompt Director] Successfully generated {len(final_scenarios)} dynamic creative scenarios via Gemini ({PROMPT_DIRECTOR_MODEL})"
            )
            return final_scenarios
        else:
            print("⚠️ [Prompt Director] Model response contained no valid scenarios after normalization.")
    except Exception as e:
        print(f"⚠️ [Prompt Director] Model generation failed: {e}")

    fallbacks = _build_fallback_scenarios(talk_title=talk_title, speaker_name=speaker_name)
    for f in fallbacks:
        _ensure_scenario_styles(f)
    return fallbacks


def format_scenarios_markdown(scenarios: Sequence[CreativeScenario]) -> str:
    """Formats scenarios into human-friendly Markdown for user preview and chat display."""
    lines = [
        "### 🎬 Creative Video Scenarios (5 shots × 2s each)",
        "Choose **one** scenario from the options below to proceed with rendering, or feel free to edit it or request new concepts.",
        "",
    ]
    for idx, sc in enumerate(scenarios, start=1):
        _ensure_scenario_styles(sc)
        lines.append(f"#### Option {idx}: {sc.title} (`{sc.genre}`)")
        lines.append(f"**Concept:** {sc.concept}\n")
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
