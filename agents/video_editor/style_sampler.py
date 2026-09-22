from __future__ import annotations

import json
import os
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .genre_scout import GenreBrief

DEFAULT_DB_PATH = Path(__file__).parent / "styles.json"


@lru_cache(maxsize=4)
def _load_styles_db_cached(path_str: str) -> Dict[str, Any]:
    target = Path(path_str)
    if not target.exists():
        # Fallback to parent Experiments/Jenres if running in development workspace
        alt_path = Path(__file__).resolve().parents[3] / "Jenres" / "styles.json"
        if alt_path.exists():
            target = alt_path
        else:
            raise FileNotFoundError(f"Cinematic styles database not found at {target} or {alt_path}.")
    with open(target, "r", encoding="utf-8") as f:
        return json.load(f)


def load_styles_db(path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Loads styles.json once per process and caches the parsed dict in-memory.

    Provides sub-millisecond lookups for video generation pipelines.
    """
    if path:
        target_str = str(path)
    else:
        env_path = os.getenv("STYLES_DB_PATH")
        target_str = env_path if env_path else str(DEFAULT_DB_PATH)
    return _load_styles_db_cached(target_str)


load_styles_db.cache_clear = _load_styles_db_cached.cache_clear  # type: ignore[attr-defined]


def filter_by_format(items: List[Dict[str, Any]], format_filter: str) -> List[Dict[str, Any]]:
    if format_filter in ["all", "wild"]:
        return items
    mapping = {
        "cinema": "feature_film",
        "film": "feature_film",
        "music_video": "music_video",
        "commercial": "commercial",
        "vlog": "documentary_vlog",
        "documentary": "documentary_vlog",
    }
    target_fmt = mapping.get(format_filter.lower(), format_filter.lower())
    filtered = [i for i in items if i.get("format") == target_fmt]
    return filtered if filtered else items


def filter_by_culture(items: List[Dict[str, Any]], culture_filter: str) -> List[Dict[str, Any]]:
    if culture_filter in ["all", "any"]:
        return items
    cult = culture_filter.lower()
    demonym_map = {
        "french": "france",
        "japanese": "japan",
        "italian": "italy",
        "german": "germany",
        "korean": "korea",
        "british": "united kingdom",
        "american": "usa",
        "russian": "ussr",
        "scandinavian": "scandinavia",
    }
    target = demonym_map.get(cult, cult)
    filtered = [
        i
        for i in items
        if target in i.get("culture_era", "").lower()
        or cult in i.get("culture_era", "").lower()
        or target in i.get("name", "").lower()
        or target in i.get("description", "").lower()
    ]
    return filtered if filtered else items


def search_styles_database(db: Dict[str, Any], query: str) -> List[tuple[str, Dict[str, Any]]]:
    """Search for relevant items across all categories by keyword query."""
    q = query.lower().strip()
    if not q:
        return []
    matches = []
    for cat in ["genres", "visual_styles", "camera_movements", "lighting", "optics_and_color"]:
        for item in db.get(cat, []):
            name = item.get("name", "").lower()
            desc = item.get("description", "").lower()
            motifs = item.get("key_motifs", "").lower()
            if q in name or q in desc or q in motifs:
                matches.append((cat, item))
    return matches


def pick_random_cinematic_styles(
    n: int = 5,
    db: Optional[Dict[str, Any]] = None,
    format_filter: str = "wild",
    culture_filter: str = "all",
    creative_guidance: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Mixes `n` completely distinct, high-entropy cinematic style profiles from the taxonomy.

    Guarantees no genre or visual style duplicates across the `n` options.
    If `creative_guidance` is provided, prioritizes items matching guidance keywords.
    """
    data = db or load_styles_db()

    all_genres = data.get("genres", [])
    all_styles = data.get("visual_styles", [])
    all_cameras = data.get("camera_movements", [])
    all_lighting = data.get("lighting", [])
    all_optics = data.get("optics_and_color", [])

    lenses = [o for o in all_optics if o.get("category") == "lens_optics"] or all_optics
    stocks = [o for o in all_optics if o.get("category") == "color_stock"] or all_optics

    # Filter genres by format and culture if specified
    filtered_genres = filter_by_format(all_genres, format_filter)
    filtered_genres = filter_by_culture(filtered_genres, culture_filter)
    if not filtered_genres:
        filtered_genres = all_genres

    # Keyword guidance matching (if user specified creative direction)
    guided_genres: List[Dict[str, Any]] = []
    guided_styles: List[Dict[str, Any]] = []
    if creative_guidance:
        keywords = [k.strip().lower() for k in re.split(r"[,;|\s]+", creative_guidance) if len(k.strip()) >= 3]
        for kw in keywords:
            for g in all_genres:
                if kw in g.get("name", "").lower() or kw in g.get("description", "").lower():
                    if g not in guided_genres:
                        guided_genres.append(g)
            for s in all_styles:
                if (
                    kw in s.get("name", "").lower()
                    or kw in s.get("description", "").lower()
                    or kw in s.get("key_motifs", "").lower()
                ):
                    if s not in guided_styles:
                        guided_styles.append(s)

    selected_results: List[Dict[str, Any]] = []
    used_genre_ids = set()
    used_style_ids = set()

    for idx in range(max(1, n)):
        # Pick genre: prioritize guidance match on first options if available
        available_genres = [g for g in filtered_genres if g.get("id") not in used_genre_ids]
        if guided_genres and idx < len(guided_genres) and guided_genres[idx].get("id") not in used_genre_ids:
            genre = guided_genres[idx]
        elif available_genres:
            genre = random.choice(available_genres)
        else:
            genre = random.choice(all_genres)
        used_genre_ids.add(genre.get("id"))

        # Pick primary visual style
        available_styles = [s for s in all_styles if s.get("id") not in used_style_ids]
        if guided_styles and idx < len(guided_styles) and guided_styles[idx].get("id") not in used_style_ids:
            primary_style = guided_styles[idx]
        elif available_styles:
            primary_style = random.choice(available_styles)
        else:
            primary_style = random.choice(all_styles)
        used_style_ids.add(primary_style.get("id"))

        # Pick secondary fusion visual style (used for Style 3 variation)
        potential_secondaries = [s for s in all_styles if s.get("id") != primary_style.get("id")]
        secondary_style = random.choice(potential_secondaries) if potential_secondaries else None

        # Camera Movement, Lighting, Lens, Stock
        camera = (
            random.choice(all_cameras)
            if all_cameras
            else {"name": "Cinematic Dolly Push-in", "description": "Smooth forward move."}
        )
        lighting = (
            random.choice(all_lighting)
            if all_lighting
            else {"name": "Chiaroscuro", "color_temp": "Warm", "description": "High-contrast directional light."}
        )
        lens = random.choice(lenses) if lenses else None
        stock = random.choice(stocks) if stocks else None

        # Synthesize ready-to-use prompt clause
        clause_parts = [
            f"Cinematic aesthetic grounded in {genre['name']} ({genre.get('culture_era', 'Cinematic')}), embodying {genre['description'].rstrip('.')}.",
            f"Visual style inspired by {primary_style['name']}, characterized by {primary_style['description'].rstrip('.')}.",
            f"Camera dynamic: {camera['name']} — {camera['description'].rstrip('.')}.",
            f"Lighting: {lighting['name']} ({lighting.get('color_temp', 'Balanced')}), {lighting['description'].rstrip('.')}.",
        ]
        if lens:
            clause_parts.append(f"Optics: {lens['name']} ({lens['description'].rstrip('.')}).")
        if stock:
            clause_parts.append(f"Color timing: {stock['name']} ({stock['description'].rstrip('.')}).")

        prompt_clause = " ".join(clause_parts)

        selected_results.append(
            {
                "genre": {
                    "id": genre.get("id", f"genre_{idx}"),
                    "name": genre["name"],
                    "format": genre.get("format", "feature_film"),
                    "culture_era": genre.get("culture_era", "Global"),
                    "description": genre["description"],
                },
                "visual_style": {
                    "id": primary_style.get("id", f"style_{idx}"),
                    "name": primary_style["name"],
                    "type": primary_style.get("type", "Style"),
                    "description": primary_style["description"],
                    "motifs": primary_style.get("key_motifs", ""),
                },
                "secondary_style": {
                    "id": secondary_style.get("id"),
                    "name": secondary_style["name"],
                    "type": secondary_style.get("type", "Style"),
                    "description": secondary_style["description"],
                    "motifs": secondary_style.get("key_motifs", ""),
                }
                if secondary_style
                else None,
                "camera_movement": {
                    "id": camera.get("id", f"cam_{idx}"),
                    "name": camera["name"],
                    "description": camera["description"],
                },
                "lighting": {
                    "id": lighting.get("id", f"light_{idx}"),
                    "name": lighting["name"],
                    "color_temp": lighting.get("color_temp", "Cinematic"),
                    "description": lighting["description"],
                },
                "optics": {
                    "id": lens.get("id") if lens else None,
                    "name": lens["name"] if lens else None,
                    "description": lens["description"] if lens else None,
                },
                "color_stock": {
                    "id": stock.get("id") if stock else None,
                    "name": stock["name"] if stock else None,
                    "description": stock["description"] if stock else None,
                },
                "prompt_clause": prompt_clause,
            }
        )

    return selected_results


def styles_to_genre_briefs(
    styles: Sequence[Dict[str, Any]],
    talk_title: str,
    speaker_name: str,
    position_company: Optional[str] = None,
    speaker_bio: Optional[str] = None,
) -> List[GenreBrief]:
    """Converts sampled style taxonomy profiles into structured GenreBrief instances.

    Each GenreBrief contains concrete cinematic parameters and attaches the raw
    style_profile dictionary as metadata for downstream directors and style variations.
    """
    briefs: List[GenreBrief] = []

    for idx, item in enumerate(styles, start=1):
        g = item["genre"]
        s = item["visual_style"]
        c = item["camera_movement"]
        light = item["lighting"]
        lens = item.get("optics") or {}
        stock = item.get("color_stock") or {}
        clause = item.get("prompt_clause", "")

        genre_clean = re.sub(r"[^a-zA-Z0-9]+", "_", g["name"].lower()).strip("_")
        style_clean = re.sub(r"[^a-zA-Z0-9]+", "_", s["name"].lower()).strip("_")
        brief_id = f"style_{idx}_{genre_clean}_{style_clean}"

        title = f"{g['name']} × {s['name']}"
        compound_genre = f"{g['name']} / {s['name']}"

        motifs_text = f" Key visual motifs: {s['motifs']}." if s.get("motifs") else ""
        visual_universe = (
            f"An immersive cinematic world grounded in {g['name']} ({g.get('culture_era', 'Cinematic')}), "
            f"embodying {g['description'].rstrip('.')}. Visual aesthetic defined by {s['name']} ({s['description'].rstrip('.')})."
            f"{motifs_text}"
        )

        tech_specs = []
        if lens.get("name"):
            tech_specs.append(f"Optics: {lens['name']}")
        if stock.get("name"):
            tech_specs.append(f"Stock: {stock['name']}")
        tech_str = f" [{'; '.join(tech_specs)}]" if tech_specs else ""

        aesthetic_manifesto = (
            f"Camera dynamic: {c['name']} ({c['description'].rstrip('.')}). "
            f"Lighting: {light['name']} [{light.get('color_temp', 'Balanced')}] ({light['description'].rstrip('.')})."
            f"{tech_str} Aesthetic clause: {clause}"
        )

        # Narrative bridge translating talk topic into visual action
        domain_str = f" in {position_company}" if position_company else ""
        narrative_metaphor = (
            f"The protagonist commands and navigates dynamic visual forces embodying '{talk_title}'{domain_str} "
            f"through decisive physical mastery native to this {g['name']} universe."
        )

        briefs.append(
            GenreBrief(
                id=brief_id,
                title=title,
                genre=compound_genre,
                visual_universe=visual_universe,
                aesthetic_manifesto=aesthetic_manifesto,
                narrative_metaphor=narrative_metaphor,
                style_profile=item,
            )
        )

    return briefs
