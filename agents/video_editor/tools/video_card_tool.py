"""Pure helpers shared by the video-editor tools (scenario resolution, result formatting)."""

from __future__ import annotations

import re
from typing import Sequence

from ..prompt_director import format_timed_omni_prompt
from ..workflow_models import CreativeScenario, RenderedAsset


def format_render_success_message(assets: Sequence[RenderedAsset], notice: str = "") -> str:
    lines = []
    if notice and isinstance(notice, str):
        lines.append(notice)
        lines.append("")
    lines.append("Generation complete.")
    for asset in assets:
        if asset.availability == "available" and asset.url:
            lines.append(f"- [{asset.label}]({asset.url})")
        else:
            lines.append(f"- {asset.label}: {asset.unavailable_reason or 'Download unavailable.'}")
    return "\n".join(lines)


def resolve_selected_scenario_prompt(
    scenarios: Sequence[CreativeScenario],
    selected_scenario_id: str | None = None,
    creative_direction: str | None = None,
) -> tuple[CreativeScenario | None, str | None, str | None]:
    """Resolves a chosen scenario or style from suggested scenarios.

    Returns:
        (matched_scenario, matched_scenario_or_style_id, resolved_prompt)
    """
    if not scenarios:
        return None, selected_scenario_id, creative_direction

    matched_sc: CreativeScenario | None = None
    matched_style: object | None = None
    matched_id: str | None = selected_scenario_id
    resolved_prompt = creative_direction

    if selected_scenario_id:
        sel_clean = selected_scenario_id.strip()
        sel_lower = sel_clean.lower()

        # 1. Option number matching: e.g. "option 2", "вариант 3", "scenario 1", "5", "option_2"
        opt_match = re.search(r"(?:option|вариант|сценарий|scenario)[_\s]*(\d+)", sel_lower) or re.match(
            r"^(\d+)$", sel_lower
        )
        if opt_match:
            idx = int(opt_match.group(1)) - 1
            if 0 <= idx < len(scenarios):
                matched_sc = scenarios[idx]
                matched_id = matched_sc.id

        # 2. Exact match on scenario ID or style ID
        if not matched_sc:
            for sc in scenarios:
                if sc.id.lower() == sel_lower:
                    matched_sc = sc
                    matched_id = sc.id
                    break
                for st in getattr(sc, "styles", []) or []:
                    if getattr(st, "id", "").lower() == sel_lower:
                        matched_sc = sc
                        matched_style = st
                        matched_id = st.id
                        break
                if matched_sc:
                    break

        # 3. Prefix or substring match (e.g. style_5_fantasy_genre_art_movement_style_1 starts with style_5_fantasy_genre_art_movement)
        if not matched_sc:
            for sc in scenarios:
                sc_id_lower = sc.id.lower()
                if sel_lower.startswith(sc_id_lower) or sc_id_lower.startswith(sel_lower):
                    matched_sc = sc
                    matched_id = sc.id
                    for st in getattr(sc, "styles", []) or []:
                        st_id_lower = getattr(st, "id", "").lower()
                        if st_id_lower == sel_lower or sel_lower.endswith(st_id_lower.split("_")[-1]):
                            matched_style = st
                            matched_id = st.id
                            break
                    break
                if sel_lower in sc.title.lower() or sc.title.lower() in sel_lower:
                    matched_sc = sc
                    matched_id = sc.id
                    break
                for st in getattr(sc, "styles", []) or []:
                    st_name = getattr(st, "name", "").lower()
                    if st_name and (st_name in sel_lower or sel_lower in st_name):
                        matched_sc = sc
                        matched_style = st
                        matched_id = getattr(st, "id", sc.id)
                        break
                if matched_sc:
                    break

    elif creative_direction:
        cd_lower = creative_direction.lower()
        for sc in scenarios:
            if sc.title.lower() in cd_lower or sc.id.lower() in cd_lower:
                matched_sc = sc
                matched_id = sc.id
                for st in getattr(sc, "styles", []) or []:
                    st_name = getattr(st, "name", "").lower()
                    st_id = getattr(st, "id", "").lower()
                    if (st_name and st_name in cd_lower) or (st_id and st_id in cd_lower):
                        matched_style = st
                        matched_id = getattr(st, "id", sc.id)
                        break
                break

    if matched_sc:
        has_timings = bool(
            resolved_prompt and any(m in resolved_prompt.lower() for m in ("00:00", "0-2s", "shot 1", "shot 2"))
        )
        if not has_timings:
            if matched_style and getattr(matched_style, "omni_prompt", None):
                sc_prompt = matched_style.omni_prompt
                shots = getattr(matched_style, "shots", None) or matched_sc.shots
                genre = getattr(matched_style, "genre", None) or matched_sc.genre
            else:
                sc_prompt = matched_sc.omni_prompt
                shots = matched_sc.shots
                genre = matched_sc.genre

            if shots and not any(m in sc_prompt.lower() for m in ("00:00", "0-2s", "shot 1")):
                sc_prompt = format_timed_omni_prompt(shots, genre, sc_prompt)
            resolved_prompt = sc_prompt

    return matched_sc, matched_id, resolved_prompt
