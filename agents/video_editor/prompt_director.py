from __future__ import annotations

import json
import os
import re
from typing import Sequence

from google.genai import types
from pydantic import BaseModel, Field

from agents.gemini_config import get_gemini_client

from .workflow_models import CreativeScenario, VideoShot

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

PROMPT_DIRECTOR_INSTRUCTION = """You are an avant-garde cinematic director and visual storyteller for cutting-edge short videos.
Your task is to transform a speaker's talk topic, title, and bio into 3 wildly imaginative, distinct cinematic mini-movie concepts.

CRITICAL RULES:
1. PROTAGONIST: The person from the portrait photo is the protagonist/character living in this universe. Do NOT analyze, evaluate, or mention their appearance, facial features, clothing, or the original background of the photo.
2. ABSOLUTELY NO PUBLIC SPEAKING: Strictly avoid any conference stages, presentation podiums, lecture halls, audiences, microphones, slide decks, or classroom settings.
3. KINEMATIC & ADVERTISING GENRES: Every scenario must be a high-production cinematic trailer, luxury sci-fi ad, cyber-thriller, surreal visual poem, neon heist, or retro-futuristic journey.
4. METAPHORICAL CONNECTION: Creatively translate the abstract themes of the talk (e.g., distributed data, neural networks, security, speed, resilience) into thrilling visual metaphors and worldbuilding.
5. 5 SHOTS x 2 SECONDS (EXACTLY 10 SECONDS TOTAL): Each scenario must consist of exactly 5 sequential shots, exactly 2 seconds each:
   - Shot 1 (00:00 - 00:02): Hook / Entrance into the world
   - Shot 2 (00:02 - 00:04): Dynamic escalation / visual metaphor in motion
   - Shot 3 (00:04 - 00:06): Intense action / peak interaction of the protagonist
   - Shot 4 (00:06 - 00:08): Dramatic climax / revelation
   - Shot 5 (00:08 - 00:10): Hero resolve / iconic hold into the final frame
6. NO ON-SCREEN TEXT OR SUBTITLES: Video will have graphics composited separately. The visual video stream must contain no rendered text, logos, or subtitles.
7. OMNI-READY PROMPT: For each scenario, combine the 5 shots into a continuous, cohesive cinematic video prompt tailored for Google Gemini Omni Flash.
"""


class _RawGeneratedScenarios(BaseModel):
    scenarios: list[CreativeScenario] = Field(default_factory=list)


def _sanitize_scenario_text(text: str) -> str:
    """Ensure no conference/stage terms seep through."""
    cleaned = text
    for term in FORBIDDEN_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", "cinematic space", cleaned, flags=re.IGNORECASE)
    return cleaned


def _build_fallback_scenarios(talk_title: str, speaker_name: str) -> list[CreativeScenario]:
    """Deterministic fallback scenarios if API call fails or runs offline."""
    base_title = talk_title or "Future Technology"
    return [
        CreativeScenario(
            id="scenario_cyberpunk",
            title="Neon Cyberpunk Odyssey",
            genre="Cyberpunk / Sci-Fi Thriller",
            concept=f"A fast-paced neon voyage through data streams visualizing '{base_title}'.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist steps onto a rain-slicked neon skyscraper rooftop, gazing at floating data ribbons.",
                    camera="Low-angle sweeping push-in, anamorphic lens flare.",
                    lighting_atmosphere="Deep moody teal and magenta neon reflections.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="They reach out, intuitively reordering luminous holographic nodes suspended in mid-air.",
                    camera="Fast orbital tracking shot, shallow depth of field.",
                    lighting_atmosphere="Glowing cyan light casting dynamic highlights on their silhouette.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="A surge of energy ripples through the city grid below, syncing with their hand gestures.",
                    camera="Dynamic overhead bird-eye diving shot toward the street grid.",
                    lighting_atmosphere="Pulsing amber and electric gold lighting bursts.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="The protagonist turns swiftly as an intricate neural lattice locks into perfect alignment.",
                    camera="Dutch angle whip-pan into a close dynamic profile.",
                    lighting_atmosphere="High-contrast split lighting with sharp chromatic edges.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="They look directly forward with calm mastery as the cyber metropolis hums harmoniously behind them.",
                    camera="Slow steady pull-back, cinematic hold.",
                    lighting_atmosphere="Golden-hour cyber twilight with soft atmospheric fog.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 cyber-thriller. "
                "Shot 1 (0-2s): Protagonist on a rain-slicked neon rooftop overlooking floating data streams, sweeping low-angle camera. "
                "Shot 2 (2-4s): Rapid orbital camera as they manipulate glowing holographic nodes in mid-air. "
                "Shot 3 (4-6s): Dynamic diving camera capturing ripples of luminous energy across a dark futuristic grid. "
                "Shot 4 (6-8s): Whip-pan to protagonist turning as a glowing neural lattice locks in place. "
                "Shot 5 (8-10s): Slow cinematic pull-back, confident heroic posture against twilight neon fog."
            ),
        ),
        CreativeScenario(
            id="scenario_deep_space",
            title="Cosmic Quantum Expedition",
            genre="Hard Sci-Fi / Interstellar",
            concept=f"An interstellar navigation through unknown quantum nebulae inspired by '{base_title}'.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist enters the observation dome of a deep-space research vessel navigating a crystalline nebula.",
                    camera="Slow forward dolly track through zero-g particle dust.",
                    lighting_atmosphere="Cool starlight with soft violet nebula glow.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="They activate an anti-gravity navigation sphere that begins orbiting between their hands.",
                    camera="Macro focus pull from the spinning quantum sphere to their determined eyes.",
                    lighting_atmosphere="Prismatic iridescent reflections on polished metallic surfaces.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="A sudden quantum jump accelerates external space into mesmerizing hyperspace light trails.",
                    camera="High-speed lateral tracking shot with smooth motion blur.",
                    lighting_atmosphere="Dazzling streaks of warm emerald and stellar white.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="The ship exits warp before an awe-inspiring glowing planetary ring system.",
                    camera="Epic grand-scale crane reveal over the protagonist's shoulder.",
                    lighting_atmosphere="Majestic golden eclipse rim-lighting.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="The protagonist stands resolute at the glass panoramic deck, watching new horizons dawn.",
                    camera="Slight rotational stabilization into a centered hero framing.",
                    lighting_atmosphere="Radiant sunrise over cosmic horizon, deep cinematic contrast.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 interstellar space expedition. "
                "Shot 1 (0-2s): Protagonist walking inside a zero-g starship observation deck into violet nebula light. "
                "Shot 2 (2-4s): Macro camera pulling focus onto a glowing quantum sphere spinning between their hands. "
                "Shot 3 (4-6s): Rapid hyperspace light trails warping past the viewport with smooth velocity. "
                "Shot 4 (6-8s): Grand reveal over their shoulder approaching an enormous glowing planetary ring. "
                "Shot 5 (8-10s): Centered heroic hold of protagonist watching cosmic sunrise, epic cinematic depth."
            ),
        ),
        CreativeScenario(
            id="scenario_surreal_nature",
            title="Solarpunk Solitude & Synthesis",
            genre="Surreal Solarpunk / High Fashion Ad",
            concept=f"A poetic visual harmony between organic nature and crystal technology representing '{base_title}'.",
            shots=[
                VideoShot(
                    shot_number=1,
                    time_range="00:00 - 00:02",
                    action="The protagonist walks through a surreal desert of black obsidian dunes dotted with blossoming bioluminescent flora.",
                    camera="Graceful low-gliding Steadicam tracking forward.",
                    lighting_atmosphere="Golden hour warm sunlight with surreal soft haze.",
                ),
                VideoShot(
                    shot_number=2,
                    time_range="00:02 - 00:04",
                    action="They gently brush their fingertips across a crystalline leaf, which chimes and sends light pulses through the earth.",
                    camera="Extreme close-up macro with 120fps slow-motion elegance.",
                    lighting_atmosphere="Sun-dappled warm amber glow with specular glitter.",
                ),
                VideoShot(
                    shot_number=3,
                    time_range="00:04 - 00:06",
                    action="Gigantic solar architectural monoliths assemble themselves soundlessly in the distant background.",
                    camera="Expansive wide lens tilt-up revealing monumental organic geometry.",
                    lighting_atmosphere="Clear architectural light, sharp clean geometric shadows.",
                ),
                VideoShot(
                    shot_number=4,
                    time_range="00:06 - 00:08",
                    action="The protagonist turns with an enigmatic, confident expression as a breeze carries glowing pollen upward.",
                    camera="360-degree rotational arc around the protagonist.",
                    lighting_atmosphere="Warm backlight catching drifting golden particles.",
                ),
                VideoShot(
                    shot_number=5,
                    time_range="00:08 - 00:10",
                    action="They stand in calm balance between nature and future architecture, looking into the camera lens.",
                    camera="Gentle cinematic push-in landing on a stunning, serene keyframe.",
                    lighting_atmosphere="Flawless editorial studio-quality natural light.",
                ),
            ],
            omni_prompt=(
                "Cinematic 9:16 solarpunk visual poem. "
                "Shot 1 (0-2s): Low-gliding camera following protagonist across black obsidian dunes with glowing flora. "
                "Shot 2 (2-4s): Macro slow-motion touch on a crystalline leaf sending ripples of light across the sand. "
                "Shot 3 (4-6s): Wide upward tilt as monumental solar geometric monoliths rise on the horizon. "
                "Shot 4 (6-8s): 360-degree rotational arc around protagonist in swirling golden breeze. "
                "Shot 5 (8-10s): Elegant centered portrait hold in radiant warm golden hour light."
            ),
        ),
    ]


def generate_creative_scenarios(
    talk_title: str,
    speaker_name: str,
    position_company: str | None = None,
    speaker_bio: str | None = None,
    count: int = 3,
) -> list[CreativeScenario]:
    """Generates 3 wildly creative 5-shot x 2-second video scenarios using gemini-3.5-flash.
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

    user_prompt = (
        f"Please invent {count} wildly different, highly creative cinematic video scenarios for this protagonist and topic.\n"
        f"CONTEXT:\n" + "\n".join(context_lines) + "\n\n"
        "Remember:\n"
        "- Protagonist is the main character.\n"
        "- NO public speaking, NO conference halls, NO stage, NO audience.\n"
        "- Invent dramatic genres (e.g. Cyberpunk, Space Exploration, Surreal Solarpunk, Retro Synthwave, Espionage Heist, Post-Apocalyptic Discovery).\n"
        "- Translate the talk topic into symbolic visual metaphors.\n"
        "- Exactly 5 shots of 2 seconds each (total 10 seconds).\n"
        "- EVERY single scenario without exception MUST have all 5 detailed shots in its 'shots' array "
        "(shot_number 1 to 5 with time_range '00:00 - 00:02', '00:02 - 00:04', '00:04 - 00:06', '00:06 - 00:08', '00:08 - 00:10', "
        "vivid action, camera dynamic, and lighting_atmosphere). Never omit or leave shots empty for any scenario.\n"
        "- Deliver a JSON object with 'scenarios' containing id, title, genre, concept, shots, and omni_prompt."
    )

    try:
        response = client.models.generate_content(
            model=PROMPT_DIRECTOR_MODEL,
            contents=[types.Part.from_text(text=user_prompt)],
            config=types.GenerateContentConfig(
                system_instruction=PROMPT_DIRECTOR_INSTRUCTION,
                temperature=1.0,
                top_p=0.95,
                response_mime_type="application/json",
                response_schema=_RawGeneratedScenarios,
            ),
        )
        if response.parsed and isinstance(response.parsed, _RawGeneratedScenarios) and response.parsed.scenarios:
            scenarios = response.parsed.scenarios
            # Clean any leakage of forbidden terms
            for s in scenarios:
                s.concept = _sanitize_scenario_text(s.concept)
                s.omni_prompt = _sanitize_scenario_text(s.omni_prompt)
                for shot in s.shots:
                    shot.action = _sanitize_scenario_text(shot.action)
                    shot.camera = _sanitize_scenario_text(shot.camera)
                    shot.lighting_atmosphere = _sanitize_scenario_text(shot.lighting_atmosphere)
            return scenarios
        elif response.text:
            data = json.loads(response.text)
            parsed = _RawGeneratedScenarios.model_validate(data)
            if parsed.scenarios:
                return parsed.scenarios
    except Exception as e:
        print(f"⚠️ [Prompt Director] Model generation failed or fell back: {e}")

    return _build_fallback_scenarios(talk_title=talk_title, speaker_name=speaker_name)


def format_scenarios_markdown(scenarios: Sequence[CreativeScenario]) -> str:
    """Formats scenarios into human-friendly Markdown for user preview and chat display."""
    lines = [
        "### 🎬 Creative Video Scenarios (5 shots × 2s each)",
        "Choose **one** scenario from the options below to proceed with rendering, or feel free to edit it or request new concepts.",
        "",
    ]
    for idx, sc in enumerate(scenarios, start=1):
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
    return "\n".join(lines)
