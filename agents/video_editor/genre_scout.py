from __future__ import annotations

import json
import os
import random
import re
import time
from typing import Any, Sequence

from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

from agents.gemini_config import get_gemini_client

GENRE_SCOUT_MODEL = os.getenv("VIDEO_GENRE_SCOUT_MODEL", "gemini-3.8-flash")

# Dynamic multidimensional catalysts organized into 5 diverse foundational pillars:
# Pillar 1: Grounded Human Realism / European Cinema / Cozy Artisanal
# Pillar 2: Classic Comedy / Whimsical Slapstick / Playful Commercial
# Pillar 3: Auteur Arthouse / High-Energy Dynamic / Poetic Realism
# Pillar 4: Visionary Solarpunk / Prismatic Future / Luminous Eco-Utopian
# Pillar 5: Constructivist Mechanical / Steampunk / Industrial Allegory

PILLAR_1_GROUNDED_REALISM = {
    "eras": [
        "1960s French New Wave (Nouvelle Vague) 35mm naturalism (Godard, Truffaut)",
        "Artisanal cozy craft commercial (warm pour-over coffee, vinyl records, tactile bakery)",
        "1970s warm Kodachrome New Hollywood road trip & diner Americana",
        "Modern European urban indie realism (sunlit loft atelier, bicycles & cobblestones)",
        "Italian 1960s Cinecittà sunny piazza & espresso bar realism",
        "Japanese quiet wabi-sabi tea house & rain-washed courtyard",
    ],
    "textures": [
        "tactile 35mm organic film grain with warm golden-hour tungsten light",
        "natural daylight bounced through tall arched windows with soft dust motes",
        "warm vintage Kodachrome color palette with rich amber and olive tones",
        "macro shallow-focus prime lens caressing wood, ceramic and coffee crema",
    ],
    "energies": [
        "warm grounded artisanal comfort & tactile human connection",
        "carefree French New Wave breezy nonchalance & candid charm",
        "cozy rainy-day introspective warmth & gentle acoustic hum",
        "sunny Mediterranean laughter, animated banter & espresso warmth",
    ],
    "environments": [
        "cozy European sidewalk café with espresso machines, warm pastries & wicker chairs",
        "sunlit artist loft atelier with giant canvas stretchers, scattered books and plants",
        "vintage vinyl record shop with spinning turntables and warm wooden shelves",
        "historic wood-paneled municipal library with rolling ladders and tall arched windows",
        "warm morning bakery with wooden counters, copper bowls and dusting flour",
        "classic roadside diner with red vinyl booths, chrome napkin holders and coffee pots",
    ],
}

PILLAR_2_CLASSIC_COMEDY = {
    "eras": [
        "Classic French visual comedy & whimsical mechanical contraptions (Jacques Tati, Pierre Richard)",
        "1920s silent slapstick comedy & mechanical stunts (Buster Keaton, Harold Lloyd)",
        "Symmetrical pastel whimsy & deadpan diorama comedy (Wes Anderson style)",
        "Playful witty Super Bowl commercial & absurd charming advertising parody",
        "1980s playful retro-arcade synthesizer adventure & comedy",
        "1950s Technicolor Hollywood musical kinetic tap-dance exuberance",
    ],
    "textures": [
        "snappy dead-center symmetrical framing with punchy pastel color blocking",
        "slapstick undercranked kinetic camera motion with rapid playful snap-zooms",
        "Technicolor three-strip saturated primary colors (canary yellow, cherry red, royal blue)",
        "hand-drawn comic accents and whimsical sound-effect visualization",
        "stop-motion tactile paper cutout textures and vibrant pop-up diorama layers",
    ],
    "energies": [
        "deadpan visual comedy, mischievous physical timing & quirky precision",
        "joyful slapstick momentum & delightful Rube Goldberg domino-effect chain reactions",
        "witty self-aware comedic energy with charming absurd transformations",
        "playful exuberance, bouncy rhythmic pacing & infectious smiles",
    ],
    "environments": [
        "quirky pastel boutique hotel lobby with brass bellboy carts and symmetrical doors",
        "1950s whimsical mechanical post office or clocktower with Rube Goldberg sorting tracks",
        "colorful Parisian cobblestone intersection with vintage bicycles and bakeries",
        "charming antique clock repair workshop with hundreds of synchronized pendulum clocks",
        "bustling morning farmers market overflowing with citrus crates, flowers and awnings",
        "retro-futuristic 1960s colorful transit terminal with playful pneumatic luggage tubes",
    ],
}

PILLAR_3_AUTEUR_ARTHOUSE = {
    "eras": [
        "Scandinavian deadpan arthouse minimalism & dry humorous irony (Roy Andersson, Aki Kaurismäki)",
        "High-energy urban athletic motivation anthem (Nike / Adidas kinetic momentum)",
        "1990s Tokyo rainy neon indie cinema (Wong Kar-wai, step-printed motion & amber mood)",
        "Eastern European poetic magical realism (gentle everyday miracles in a historic city)",
        "Minimalist architectural modern keynote commercial (Apple studio daylight & clean lines)",
        "Atmospheric 1940s film noir detective mystery with expressive Venetian blind shadows",
    ],
    "textures": [
        "anamorphic horizontal blue lens streaks and cinematic wide letterbox depth",
        "step-printed slow shutter motion blur with vibrant neon light trails",
        "clean architectural high-key natural daylight with pristine glass reflections",
        "expressive black-and-white silver-gelatin contrast with dramatic directional lighting",
        "10,000fps ultra slow-motion fluid droplet splashes & visceral macro sweat droplets",
    ],
    "energies": [
        "high-velocity kinetic athletic drive, breath and unstoppable momentum",
        "wry dry Scandinavian irony with deadpan unhurried comedic brilliance",
        "hypnotic urban nocturnal poetry, neon reflections and nostalgic romance",
        "lyrical magical realism with soaring wonder and unexpected beauty",
        "tense suspenseful clockwork countdown & razor-sharp precision",
    ],
    "environments": [
        "misty morning riverside suspension bridge with running silhouettes against sunrise",
        "rain-slicked midnight urban alley reflecting emerald and amber neon signs",
        "minimalist concrete and glass art gallery pavilion overlooking a quiet autumn park",
        "atmospheric historic jazz club with brass saxophones, velvet curtains and warm lights",
        "grand European train station concourse with soaring steel ribs and sunbeams slicing steam",
        "sunlit architectural rooftop greenhouse overlooking a panoramic historic city skyline",
    ],
}

PILLAR_4_VISIONARY_SOLARPUNK = {
    "eras": [
        "Visionary Solarpunk & Eco-Utopian future (lush vertical bio-architecture, crystal solar monoliths)",
        "Prismatic Levitation Odyssey (floating crystalline prisms, refracted laser spectrums, zero-gravity elegance)",
        "Futuristic Botanical Observatory (bioluminescent flora, soaring glass geodesic domes, clean optimism)",
        "Luminous Aero-Solar Metropolis (floating sky-gardens, solar sails, crystalline clean energy towers)",
        "Celestial High-Tech Planetarium (curved holographic astrolabes, star-mapping lasers, weightless wonder)",
    ],
    "textures": [
        "refracted prism caustics and radiant iridescent rainbow light flares",
        "translucent quartz glass, living emerald bioluminescent moss and pure white titanium surfaces",
        "crystalline anamorphic horizontal flares with soft ethereal bloom",
        "zero-gravity floating water droplets refracting golden sunlight",
        "luminous holographic interface geometry suspended in clean mountain air",
    ],
    "energies": [
        "breathless cosmic wonder, visionary serenity & boundless optimism",
        "harmonious bio-digital resonance & weightless celestial elegance",
        "vibrant radiant euphoria, luminous intelligence & soaring curiosity",
        "serene meditative stillness punctuated by breathtaking light revelations",
    ],
    "environments": [
        "soaring solar-glass cathedral with levitating crystalline prisms catching sunrise beams",
        "verdant floating sky-terrace overlooking a pristine solarpunk city of gleaming white spirals",
        "bioluminescent botanical conservatory with towering glass arches and glowing exotic flora",
        "crystalline clean-room observatory cantilevered over an emerald cloud canopy",
        "sunlit holographic planetarium chamber with orbiting miniature light planets",
    ],
}

PILLAR_5_CONSTRUCTIVIST_MECHANICAL = {
    "eras": [
        "Constructivist Mechanical Allegory (colossal soot-black steel girders, giant bronze gears, flywheels)",
        "Steampunk Subterranean Clockwork (heavy counterweights, brass pistons, glowing vacuum tubes, steam vents)",
        "1920s Bauhaus / Avant-Garde Industrial Dynamo (geometric levers, spinning flywheels, kinetic precision)",
        "High-End Industrial Craft Commercial (hand-forged damascus steel, roaring bronze furnace, athletic mastery)",
        "Retro-Futuristic Mission Control (banks of glowing analog dials, tactile toggle switches, oscilloscope waves)",
    ],
    "textures": [
        "analog risograph halftone dot texture overlay with matte charcoal and raw bronze tones",
        "heavy cast-iron patina, polished brass gears, and curling plumes of backlit white steam",
        "dramatic chiaroscuro tungsten furnace glow carving muscular silhouettes against giant gears",
        "tactile oil-sheened steel, macro rivet details and sparking kinetic friction",
        "warm orange nixie tube digits glowing inside glass vacuum envelopes",
    ],
    "energies": [
        "colossal tectonic power, unstoppable mechanical momentum & athletic mastery",
        "mesmerizing hypnotic clockwork precision & synchronized kinetic heartbeat",
        "raw industrial forge passion, sparks and heroic physical achievement",
        "exhilarating countdown tension and tactile analog switchboard mastery",
    ],
    "environments": [
        "monumental subterranean clockwork chamber with gargantuan interlocking bronze gears and flywheels",
        "dramatic industrial foundry cathedral with towering steel trusses and glowing crucible cauldrons",
        "vintage avant-garde locomotive roundhouse with steam vents, iron catwalks and brass telegraphs",
        "steampunk astronomical clocktower filled with nested astrolabes and counterweight pulleys",
        "retro-futuristic deep-underground vault with towering copper solenoid banks and glowing vacuum tubes",
    ],
}

# Flatted catalyst lists for backward compatibility
ERA_PARADIGMS: list[str] = (
    PILLAR_1_GROUNDED_REALISM["eras"]
    + PILLAR_2_CLASSIC_COMEDY["eras"]
    + PILLAR_3_AUTEUR_ARTHOUSE["eras"]
    + PILLAR_4_VISIONARY_SOLARPUNK["eras"]
    + PILLAR_5_CONSTRUCTIVIST_MECHANICAL["eras"]
)
OPTICAL_MEDIUM_TEXTURES: list[str] = (
    PILLAR_1_GROUNDED_REALISM["textures"]
    + PILLAR_2_CLASSIC_COMEDY["textures"]
    + PILLAR_3_AUTEUR_ARTHOUSE["textures"]
    + PILLAR_4_VISIONARY_SOLARPUNK["textures"]
    + PILLAR_5_CONSTRUCTIVIST_MECHANICAL["textures"]
)
TONAL_MOOD_ENERGIES: list[str] = (
    PILLAR_1_GROUNDED_REALISM["energies"]
    + PILLAR_2_CLASSIC_COMEDY["energies"]
    + PILLAR_3_AUTEUR_ARTHOUSE["energies"]
    + PILLAR_4_VISIONARY_SOLARPUNK["energies"]
    + PILLAR_5_CONSTRUCTIVIST_MECHANICAL["energies"]
)
SPATIAL_ENVIRONMENTS: list[str] = (
    PILLAR_1_GROUNDED_REALISM["environments"]
    + PILLAR_2_CLASSIC_COMEDY["environments"]
    + PILLAR_3_AUTEUR_ARTHOUSE["environments"]
    + PILLAR_4_VISIONARY_SOLARPUNK["environments"]
    + PILLAR_5_CONSTRUCTIVIST_MECHANICAL["environments"]
)

# Backward-compatible reference cluster map
AESTHETIC_CLUSTERS: dict[str, list[dict[str, str]]] = {
    "grounded_realism": [
        {"name": "French New Wave", "vibe": "Handheld 35mm natural daylight, Parisian bistro candid realism"},
        {"name": "Artisanal Cozy Craft", "vibe": "Warm pour-over coffee, vinyl turntables, morning bakery comfort"},
    ],
    "classic_comedy": [
        {"name": "Jacques Tati Visual Slapstick", "vibe": "Eccentric mechanical contraptions, deadpan comedic timing"},
        {
            "name": "Wes Anderson Whimsical Diorama",
            "vibe": "Pastel color blocking, planimetric symmetry, charming eccentricity",
        },
    ],
    "auteur_arthouse": [
        {"name": "Scandinavian Deadpan Arthouse", "vibe": "Wry understated humor, soft muted palette, dry ironies"},
        {
            "name": "High-Velocity Kinetic Anthem",
            "vibe": "Explosive urban morning run, athletic momentum and raw drive",
        },
    ],
    "solarpunk_prismatic": [
        {
            "name": "Visionary Solarpunk Odyssey",
            "vibe": "Lush vertical bio-architecture, levitating prisms, radiant optimism",
        },
        {
            "name": "Prismatic Light Cathedral",
            "vibe": "Floating crystalline optics, refracted laser spectrums, ethereal serenity",
        },
    ],
    "constructivist_mechanical": [
        {
            "name": "Constructivist Clockwork Allegory",
            "vibe": "Colossal interlocking bronze gears, risograph halftone textures, athletic hoist",
        },
        {
            "name": "Steampunk Subterranean Dynamo",
            "vibe": "Heavy counterweights, brass pistons, glowing vacuum tubes, steam vents",
        },
    ],
}


class GenreBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(description="Unique snake_case identifier (e.g. noir_whisper, solar_botanica)")
    title: str = Field(description="Catchy, evocative cinematic mini-film title")
    genre: str = Field(description="Distinct newly invented genre label or visual movement")
    visual_universe: str = Field(description="Vivid description of the environment, era, textures, and world")
    aesthetic_manifesto: str = Field(
        description="Lighting style, color grade, camera movement philosophy, and lens choices"
    )
    narrative_metaphor: str = Field(
        description="How the speaker's topic is creatively turned into hero action in this world"
    )


class _RawScoutResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    genres: list[GenreBrief] = Field(default_factory=list)


def sample_creative_archetypes(count: int = 5) -> list[dict[str, str]]:
    """Stochastically synthesizes `count` dynamic, non-overlapping multi-axis catalyst sparks.

    Draws sequentially across our five distinct creative pillars:
    - Pillar 1: Grounded Human Realism / European Cinema / Cozy Artisanal
    - Pillar 2: Classic Comedy / Whimsical Slapstick / Playful Commercial
    - Pillar 3: Auteur Arthouse / High-Energy Dynamic / Poetic Realism
    - Pillar 4: Visionary Solarpunk / Prismatic Future / Luminous Eco-Utopian
    - Pillar 5: Constructivist Mechanical / Steampunk / Industrial Allegory
    This guarantees every run produces a wildly diverse, balanced spectrum spanning realism, comedy, arthouse, solarpunk, and constructivist fantasy.
    """
    pillars = [
        PILLAR_1_GROUNDED_REALISM,
        PILLAR_2_CLASSIC_COMEDY,
        PILLAR_3_AUTEUR_ARTHOUSE,
        PILLAR_4_VISIONARY_SOLARPUNK,
        PILLAR_5_CONSTRUCTIVIST_MECHANICAL,
    ]
    sampled: list[dict[str, str]] = []

    for i in range(count):
        p = pillars[i % len(pillars)]
        era = random.choice(p["eras"])
        texture = random.choice(p["textures"])
        energy = random.choice(p["energies"])
        env = random.choice(p["environments"])

        mood_keyword = energy.split()[0].title()
        era_words = [
            w
            for w in era.split()
            if w.lower() not in {"and", "&", "the", "with", "silent", "(godard,", "(wes", "(jacques"}
        ]
        era_keyword = era_words[0].title() if era_words else "Cinematic"
        texture_keyword = texture.split()[0].title()
        compound_name = f"{mood_keyword}-{texture_keyword} {era_keyword}"

        dynamic_vibe = f"Fuses {era} with {texture}, pulsating with {energy} inside {env}."

        sampled.append(
            {
                "name": compound_name,
                "vibe": dynamic_vibe,
                "era": era,
                "texture": texture,
                "energy": energy,
                "environment": env,
            }
        )
    return sampled


GENRE_SCOUT_INSTRUCTION = """You are an international film festival curator, commercial director, and master storyteller.
Your singular objective is to create a BALANCED, VIBRANT, WILDLY DIVERSE SPECTRUM of 5 contrasting cinematic worlds for a 10-second hero video featuring the protagonist.

CRITICAL CREATIVE LAWS:
1. STRICT BAN ON POST-APOCALYPTIC & MONOTONOUS TROPES:
   - ABSOLUTELY DO NOT default to scorched earth, barren deserts, salt flats, obsidian ruins, or post-apocalyptic wastelands!
   - Ground realism in living, textured environments (cozy European cafés, bustling bakeries, sunlit lofts, quirky boutique hotels, rainy bridges).
   - For sci-fi and fantasy, focus on luminous, breathtaking wonders (crystalline solarpunk cathedrals, floating solar sails, bio-conservatories, or colossal brass and steel clockwork mechanisms) rather than bleak deserts!
2. GUARANTEE A RICH 5-PILLAR MULTI-GENRE MIX:
   Your 5 options MUST explore five completely different cinematic, commercial, and visionary genres:
   - Option 1: Grounded Human Realism / European Cinema / Cozy Artisanal (warm, relatable, living world — French New Wave daylight, cozy coffee & vinyl craft, or indie cinema realism)
   - Option 2: Classic Comedy / Whimsical Slapstick / Playful Commercial (visual humor, eccentric Rube Goldberg contraptions, Jacques Tati / Buster Keaton timing, Wes Anderson pastel symmetry, or playful Super Bowl commercial charm)
   - Option 3: Auteur Arthouse / High-Energy Dynamic / Poetic Realism (Scandinavian deadpan irony, high-velocity sports motivation, Wong Kar-wai neon poetry, or lyrical magical realism)
   - Option 4: Visionary Solarpunk / Prismatic Future / Luminous Eco-Utopian (levitating crystalline prisms, solar monoliths, lush bio-architecture, clean optimism, floating kinetic light sculptures)
   - Option 5: Constructivist Mechanical / Steampunk / Industrial Allegory (colossal brass and steel clockwork, counterweights, flywheels, athletic hoist, risograph halftone textures, power & momentum)
3. INVENT EVOCATIVE COMPOUND GENRE NAMES:
   - Do NOT use plain textbook tags like "Sci-Fi" or "Comedy".
   - Create fresh, memorable compound genre labels, such as:
     * "Jacques-Tati Mechanical Slapstick Comedy"
     * "French New Wave Parisian Daylight Realism"
     * "Prismatic Solarpunk Levitation Odyssey"
     * "Constructivist Clockwork Industrial Allegory"
     * "Wes-Anderson Symmetrical Pastel Parable"
     * "High-Velocity Urban Sunrise Sports Anthem"
     * "Scandinavian Deadpan Arthouse Irony"
4. PROTAGONIST IS THE HERO: The person from the portrait is the active hero/protagonist enjoying or mastering this world. Do NOT critique their appearance or photo.
5. STRICTLY ZERO REAL NAMES: NEVER output or reveal the speaker's real personal name in any genre names, titles, concepts, visual universes, or narrative metaphors. Always refer to the character as "the protagonist" or "the hero".
6. STRICTLY ZERO PUBLIC SPEAKING: Absolutely NO stages, microphones, audiences, presentation podiums, slide decks, or lecture halls.
7. METAPHORICAL GENIUS & BIO FUSION:
   - Boldly synthesize the speaker's specific talk topic (e.g. databases, concurrency, Agentic Web, AI agents, WebMCP) AND their personal background, hobbies, or bio details (e.g. powerlifting, athletics, botany, astronomy, music, photography) into tactile, sensory, unforgettable visual actions.
   - In `narrative_metaphor`, explicitly explain the clever metaphorical bridge connecting their talk topic/bio to their hero action in this world.
"""


def scout_creative_genres(
    talk_title: str,
    speaker_name: str,
    position_company: str | None = None,
    speaker_bio: str | None = None,
    creative_guidance: str | None = None,
    count: int = 5,
) -> list[GenreBrief]:
    """Stage 1: Generates 5 radically diverse, non-formulaic creative genres.
    Samples 5 distinct architectural pillars and fuses them with the talk topic & speaker bio.
    """
    client = get_gemini_client()

    # Sample random archetypes from distinct clusters
    sampled_seeds = sample_creative_archetypes(count=count)
    seeds_text = "\n".join(
        f"- Spark {i + 1} Dimensional Catalyst:\n"
        f"  * Era / Paradigm Impulse: {s.get('era', s['name'])}\n"
        f"  * Optical / Medium Texture: {s.get('texture', 'Dynamic lens texture')}\n"
        f"  * Mood / Rhythmic Energy: {s.get('energy', 'High kinetic energy')}\n"
        f"  * Spatial Environment: {s.get('environment', 'Cinematic landscape')}\n"
        f"  * Synthesis Hint: {s['name']} ({s['vibe']})"
        for i, s in enumerate(sampled_seeds)
    )

    context_lines = [
        f"Talk Title: {talk_title}",
        "Protagonist / Hero: The protagonist (ANONYMOUS: NEVER write or output real personal names in genres or concepts)",
    ]
    if position_company:
        context_lines.append(f"Domain / Topic: {position_company}")
    if speaker_bio:
        context_lines.append(f"Background & Expertise: {speaker_bio}")
    if creative_guidance:
        context_lines.append(f"User Requested Tone & Style Direction: {creative_guidance}")

    guidance_instruction = ""
    if creative_guidance:
        guidance_instruction = (
            f"\nSPECIAL USER DIRECTION: The user explicitly specified: '{creative_guidance}'. "
            "Incorporate this direction while still ensuring each of the 5 options explores a fresh, distinct creative interpretation!\n"
        )

    prompt = (
        f"Synthesize {count} completely original, wildly contrasting, UNEXPECTED genre briefs for a 10-second cinematic hero video.\n\n"
        f"CONTEXT:\n" + "\n".join(context_lines) + "\n"
        f"{guidance_instruction}\n"
        f"STOCHASTIC MULTI-AXIS CATALYST SPARKS (Use these orthogonal dimensions as raw creative fuel to invent brand-new compound genres):\n"
        f"{seeds_text}\n\n"
        "REQUIREMENTS FOR EACH GENRE BRIEF (RICH 5-PILLAR SPECTRUM: REALISM, COMEDY, ARTHOUSE, SOLARPUNK, & CONSTRUCTIVIST STEAMPUNK):\n"
        "- NO POST-APOCALYPTIC WASTELANDS: Ground realism in living cities, cozy rooms, cafes, libraries, bakeries, or ateliers. In sci-fi/fantasy, create luminous, awe-inspiring solarpunk or majestic clockwork mechanisms, avoiding scorched dunes, salt flats, and obsidian ruins!\n"
        "- MULTI-GENRE DIVERSITY:\n"
        "  * Option 1: Grounded Human Realism / European Cinema / Cozy Artisanal (warm living world, French New Wave naturalism, cafe or workshop)\n"
        "  * Option 2: Classic Comedy / Whimsical Slapstick / Playful Commercial (visual humor, eccentric Rube Goldberg contraptions, Jacques Tati / Buster Keaton timing, Wes Anderson pastel symmetry, or playful advertising parody)\n"
        "  * Option 3: Auteur Arthouse / High-Energy Dynamic / Poetic Realism (Scandinavian deadpan, sports momentum, or lyrical visual poetry)\n"
        "  * Option 4: Visionary Solarpunk / Prismatic Future / Luminous Eco-Utopian (levitating crystalline prisms, solar monoliths, lush bio-architecture, clean optimism, floating kinetic light sculptures)\n"
        "  * Option 5: Constructivist Mechanical / Steampunk / Industrial Allegory (colossal brass and steel clockwork, counterweights, flywheels, athletic hoist, risograph halftone textures, power & momentum)\n"
        "- `id`: Unique snake_case identifier (e.g. tati_bakery_contraption, new_wave_paris_cafe, kinetic_sunrise_run, solarpunk_prism_sky, constructivist_clockwork)\n"
        "- `title`: Punchy, memorable, poetic or witty title for this visual concept\n"
        "- `genre`: Brand-new invented compound genre label (e.g. 'Jacques-Tati Mechanical Slapstick Comedy', 'French New Wave Parisian Daylight Realism', 'Prismatic Solarpunk Levitation Odyssey', 'Constructivist Mechanical Allegory')\n"
        "- `visual_universe`: 2-3 vivid sentences describing the physical world, tactile textures, lighting atmosphere, and environment\n"
        "- `aesthetic_manifesto`: Camera philosophy, lens choices, color grading palette, and rhythmic pacing\n"
        "- `narrative_metaphor`: A clear, inspiring sentence explicitly connecting the speaker's topic (and personal bio/hobbies if available) to the tactile visual quest or interaction in this world\n\n"
        f"Return a JSON object with a 'genres' list of {count} items."
    )

    retries = 2
    delay = 1.0
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=GENRE_SCOUT_MODEL,
                contents=[types.Part.from_text(text=prompt)],
                config=types.GenerateContentConfig(
                    system_instruction=GENRE_SCOUT_INSTRUCTION,
                    temperature=1.6,  # Maximum creative entropy
                    top_p=0.98,
                    response_mime_type="application/json",
                ),
            )
            raw_list: list[Any] = []
            if response.parsed and getattr(response.parsed, "genres", None):
                raw_list = response.parsed.genres
            elif response.text:
                cleaned_json = response.text.strip()
                if cleaned_json.startswith("```"):
                    cleaned_json = re.sub(r"^```(?:json)?\n?", "", cleaned_json)
                    cleaned_json = re.sub(r"\n?```$", "", cleaned_json).strip()
                data = json.loads(cleaned_json)
                raw_list = (
                    data.get("genres", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                )

            briefs: list[GenreBrief] = []
            for idx, entry in enumerate(raw_list, start=1):
                if isinstance(entry, dict):
                    gid = entry.get("id") or f"genre_concept_{idx}"
                    title = _sanitize_genre_text(entry.get("title") or f"Concept {idx}", speaker_name)
                    genre = _sanitize_genre_text(
                        entry.get("genre") or sampled_seeds[min(idx - 1, len(sampled_seeds) - 1)]["name"],
                        speaker_name,
                    )
                    vu = _sanitize_genre_text(
                        entry.get("visual_universe") or "A highly stylized cinematic environment.", speaker_name
                    )
                    am = _sanitize_genre_text(
                        entry.get("aesthetic_manifesto") or "Dynamic camera work with dramatic lighting.", speaker_name
                    )
                    nm = _sanitize_genre_text(
                        entry.get("narrative_metaphor")
                        or f"The protagonist engages with the core concepts of {talk_title}.",
                        speaker_name,
                    )
                    briefs.append(
                        GenreBrief(
                            id=gid,
                            title=title,
                            genre=genre,
                            visual_universe=vu,
                            aesthetic_manifesto=am,
                            narrative_metaphor=nm,
                        )
                    )

            if len(briefs) >= count:
                print(
                    f"🎨 [Genre Scout] Discovered {len(briefs)} radical genre concepts via Gemini ({GENRE_SCOUT_MODEL})"
                )
                return briefs[:count]
            elif briefs:
                print(f"🎨 [Genre Scout] Produced {len(briefs)} briefs; padding to {count} with stochastic fallbacks.")
                while len(briefs) < count:
                    briefs.append(_build_fallback_brief(talk_title, speaker_name, len(briefs) + 1, sampled_seeds))
                return briefs
            else:
                print("⚠️ [Genre Scout] Model returned no parseable genres. Using stochastic fallback matrix.")
                break
        except Exception as e:
            err_str = str(e).lower()
            is_transient = any(
                marker in err_str
                for marker in ("429", "resource_exhausted", "too many requests", "quota", "503", "unavailable")
            )
            if attempt < retries - 1 and is_transient:
                time.sleep(delay)
                delay *= 2
                continue
            print(f"⚠️ [Genre Scout] Generation failed: {e}. Falling back to stochastic archetype matrix.")
            break

    return [_build_fallback_brief(talk_title, speaker_name, i + 1, sampled_seeds) for i in range(count)]


def _sanitize_genre_text(text: str, speaker_name: str | None = None) -> str:
    cleaned = text
    if speaker_name:
        cleaned = re.sub(rf"\b{re.escape(speaker_name.strip())}\b", "the protagonist", cleaned, flags=re.IGNORECASE)
        for part in speaker_name.split():
            if len(part) >= 3 and part.lower() not in {"and", "the", "van", "von", "de", "del"}:
                cleaned = re.sub(rf"\b{re.escape(part)}\b", "the protagonist", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bthe protagonist(?:\s+the protagonist)+\b", "the protagonist", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bthe protagonist\s*'?s\b", "the protagonist's", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"(^|[:.!?]\s+)the protagonist\b", r"\1The protagonist", cleaned)
    return cleaned


def _build_fallback_brief(
    talk_title: str, speaker_name: str, index: int, sampled_seeds: list[dict[str, str]]
) -> GenreBrief:
    seed = sampled_seeds[min(index - 1, len(sampled_seeds) - 1)]
    era = seed.get("era", seed["name"])
    texture = seed.get("texture", "tactile cinematic texture")
    energy = seed.get("energy", "kinetic rhythm")
    env = seed.get("environment", "surreal cinematic world")

    # Dynamically synthesize compound genre name and title
    mood_word = energy.split()[0].title()
    texture_word = texture.split()[0].title()
    era_word = [w for w in era.split() if w.lower() not in {"and", "&", "the", "with", "silent"}][-1].title()
    compound_genre = f"{mood_word}-{texture_word} {era_word}"

    topic_clean = talk_title.split()[-1].title() if talk_title else "Horizon"
    slug = re.sub(r"[^a-z0-9]+", "_", compound_genre.lower()).strip("_")

    return GenreBrief(
        id=f"{slug}_{index}",
        title=f"{compound_genre}: The {topic_clean} Odyssey",
        genre=compound_genre,
        visual_universe=f"An original cinematic environment in {env}, shaped by {era} and textured with {texture}.",
        aesthetic_manifesto=f"Visual direction vibrating with {energy}. High-contrast grading, tactile optics, and dynamic camera choreography.",
        narrative_metaphor=f"The protagonist commands and navigates dynamic visual forces embodying '{talk_title}'.",
    )
