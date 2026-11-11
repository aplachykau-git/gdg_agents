"""MCP server exposing the studio's heavy tools to any MCP client (Claude, Gemini CLI, IDEs).

It reuses the same framework-independent core as the ADK agents, so behaviour is identical to the
web studio; the MCP client (the model) keeps the conversation, so every tool is stateless.

Run locally (stdio, the client starts it):
    uv run python -m agents.mcp_server
Run as an HTTP service (streamable HTTP at /mcp, bearer token required):
    MCP_AUTH_TOKEN=... uv run python -m agents.mcp_server --http --port 8090

VIDEO_EDITOR_OFFLINE=true makes scenarios and renders free and instant (sample output).
"""

from __future__ import annotations

import os

# stdout carries the MCP protocol in stdio mode: logs must go to stderr, before anything logs.
os.environ.setdefault("LOG_STREAM", "stderr")

import argparse  # noqa: E402
import asyncio  # noqa: E402
import logging  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402
from urllib.parse import urlparse  # noqa: E402

from agents.bootstrap import initialise_agent_environment  # noqa: E402

initialise_agent_environment()

from mcp.server.mcpserver import MCPServer  # noqa: E402

from agents.common import ui_payloads  # noqa: E402
from agents.video_editor import video_card_service as cards  # noqa: E402
from agents.video_editor.workflow_models import ValidationFailure, VideoEditorDraft  # noqa: E402

logger = logging.getLogger(__name__)

INSTRUCTIONS = """Community AI Studio tools for meetup organisers.

Speaker-card video: 1) propose_video_scenarios, 2) let the user pick a scenario (and optionally a style),
3) start_speaker_card_render with that option's `creative_direction` and the speaker photo,
4) poll get_render_status every ~20 s until status is `done` (renders take 1-3 minutes).
Never invent scenarios yourself; always show the ones returned by the tool.
"""

mcp = MCPServer(name="community-studio", instructions=INSTRUCTIONS)


# --------------------------------------------------------------------------- render jobs


@dataclass
class RenderJob:
    id: str
    created: float = field(default_factory=time.time)
    status: str = "running"  # running | done | failed
    result: dict[str, Any] = field(default_factory=dict)
    task: asyncio.Task | None = None


JOBS: dict[str, RenderJob] = {}
MAX_FINISHED_JOBS = 50


def _forget_old_jobs() -> None:
    finished = sorted((j for j in JOBS.values() if j.status != "running"), key=lambda j: j.created)
    for job in finished[:-MAX_FINISHED_JOBS]:
        JOBS.pop(job.id, None)


def _download(url: str, target_dir: Path) -> Path:
    import requests

    suffix = Path(urlparse(url).path).suffix or ".jpg"
    target = target_dir / f"source{suffix}"
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(target, "wb") as handle:
            shutil.copyfileobj(response.raw, handle)
    return target


async def _run_render(job: RenderJob, draft: VideoEditorDraft, source: str) -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="mcp-render-"))
    try:
        if source.startswith(("http://", "https://")):
            path = await asyncio.to_thread(_download, source, tmp_dir)
        else:
            path = Path(source).expanduser()
        if cards.offline_mode():
            rendered = await cards.offline_render(draft)
        else:
            rendered = await cards.render_card(
                draft,
                cards.RenderSettings(),
                stage_media=cards.stage_local_file(path),
                workspace_label=f"mcp-{job.id}",
            )
        if isinstance(rendered, ValidationFailure):
            job.status = "failed"
            job.result = {"code": rendered.code, "message": rendered.message, "retryable": rendered.retryable}
            return
        assets = [asset.model_dump(mode="json") for asset in rendered.assets]
        job.status = "done"
        job.result = {
            "assets": assets,
            "urls": ui_payloads.media(assets)["urls"],
            "notice": rendered.notice or "",
        }
    except Exception as error:  # surfaced to the client instead of killing the server
        logger.exception("Render job %s failed", job.id)
        job.status = "failed"
        job.result = {"code": "render_failed", "message": str(error), "retryable": True}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# --------------------------------------------------------------------------- tools


def _scenario_summary(index: int, scenario: Any) -> dict[str, Any]:
    return {
        "option": index,
        "id": scenario.id,
        "title": scenario.title,
        "genre": scenario.genre,
        "concept": scenario.concept,
        "shots": [f"{shot.time_range}: {shot.action}" for shot in scenario.shots],
        "creative_direction": scenario.omni_prompt,
        "styles": [
            {"id": style.id, "name": style.name, "creative_direction": style.omni_prompt} for style in scenario.styles
        ],
    }


@mcp.tool()
async def propose_video_scenarios(
    talk_title: str,
    name: str,
    position_company: str,
    speaker_bio: str = "",
    guidance: str = "",
) -> dict[str, Any]:
    """Invent 5 cinematic scenarios (5 shots x 2 s) for an animated speaker card.

    Args:
        talk_title: Talk title shown on the card.
        name: Speaker full name.
        position_company: Position and company, e.g. "Senior SRE, DualEntry".
        speaker_bio: Optional bio or talk abstract to tailor the ideas.
        guidance: Optional wish, e.g. "like a Nike ad", "more humour".
    """
    scenarios = await asyncio.to_thread(
        cards.generate_scenarios,
        talk_title=talk_title,
        speaker_name=name,
        position_company=position_company,
        speaker_bio=speaker_bio or None,
        creative_guidance=guidance or None,
    )
    return {"scenarios": [_scenario_summary(i, sc) for i, sc in enumerate(scenarios, start=1)]}


@mcp.tool()
async def start_speaker_card_render(
    photo: str,
    talk_title: str,
    name: str,
    position_company: str,
    creative_direction: str = "",
) -> dict[str, Any]:
    """Start rendering the speaker-card video (takes 1-3 minutes). Poll get_render_status with the job_id.

    Args:
        photo: Portrait photo or speaker video: a local file path or an http(s) URL.
        talk_title: Talk title shown on the card.
        name: Speaker full name.
        position_company: Position and company.
        creative_direction: The chosen scenario's or style's `creative_direction` (needed for photos).
    """
    draft = VideoEditorDraft(
        title=talk_title, name=name, position_company=position_company, creative_direction=creative_direction or None
    )
    job = RenderJob(id=uuid.uuid4().hex[:12])
    JOBS[job.id] = job
    job.task = asyncio.create_task(_run_render(job, draft, photo))
    _forget_old_jobs()
    return {"job_id": job.id, "status": job.status}


@mcp.tool()
async def get_render_status(job_id: str) -> dict[str, Any]:
    """Status of a render started with start_speaker_card_render: running, done (with urls) or failed.

    Args:
        job_id: The id returned by start_speaker_card_render.
    """
    job = JOBS.get(job_id)
    if job is None:
        return {"status": "unknown", "message": "No such job (the server may have been restarted)."}
    return {"job_id": job.id, "status": job.status, "elapsed_seconds": round(time.time() - job.created), **job.result}


@mcp.tool()
async def process_registration_list(file_path: str, capacity: int = 0, manual_confirmed: str = "") -> dict[str, Any]:
    """Clean, deduplicate and split an attendee list (CSV/XLSX) into confirmed and waitlist; writes a DOCX roster.

    Args:
        file_path: Path to the CSV or Excel export.
        capacity: Venue capacity; 0 keeps the statuses from the file.
        manual_confirmed: Comma- or newline-separated names that must be confirmed.
    """
    from agents.registration_manager.tools import process_registrations

    result = await asyncio.to_thread(process_registrations, file_path, capacity, manual_confirmed)
    if isinstance(result, str):  # error message
        return {"status": "error", "message": result}
    ui = result.get("ui") or {}
    return {"status": "ok", "summary": result["result"], "document": ui.get("url"), "roster": ui.get("roster_text")}


@mcp.tool()
async def scan_receipt(file_path: str) -> dict[str, Any]:
    """Extract items, totals and currency from a receipt or invoice (image or PDF).

    Args:
        file_path: Path to the receipt file.
    """
    from agents.receipt_scanner.tools import read_receipt_file

    return await asyncio.to_thread(read_receipt_file, file_path)


@mcp.tool()
async def generate_qr_code(
    link: str,
    color: str = "",
    background: str = "",
    eye_color: str = "",
    transparent_background: bool = False,
    output_dir: str = "",
) -> dict[str, Any]:
    """Create a rounded QR code for a link and save it as a flat vector SVG and a 1024px PNG.

    Args:
        link: Link or text to encode; a bare domain gets https:// added.
        color: Hex colour of the modules (default black).
        background: Hex background colour (default white).
        eye_color: Hex colour of the corner eyes (default = color).
        transparent_background: Leave the background transparent.
        output_dir: Folder for the files (default agents/qr_code_generator/results).
    """
    from agents.qr_code_generator.qr_render import QrStyle, build_qr, normalize_link
    from agents.qr_code_generator.tools import RESULTS_DIR, save_qr

    try:
        style = QrStyle(
            color=color.strip() or "#000000",
            background=background.strip() or "#FFFFFF",
            eye_color=eye_color.strip() or None,
            transparent=transparent_background,
        )
        result = await asyncio.to_thread(build_qr, normalize_link(link), style)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    paths = save_qr(result, style, Path(output_dir).expanduser() if output_dir else RESULTS_DIR)
    return {"status": "ok", "link": result.data, "svg": str(paths["svg"]), "png": str(paths["png"])}


# --------------------------------------------------------------------------- entry point


def _http_app(token: str):
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    app = mcp.streamable_http_app()

    class BearerAuth(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.headers.get("authorization", "") != f"Bearer {token}":
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    app.add_middleware(BearerAuth)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8090")))
    args = parser.parse_args()
    if not args.http:
        mcp.run()
        return
    token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    if not token:
        raise SystemExit("MCP_AUTH_TOKEN is required for --http (the tools spend API credits).")
    import uvicorn

    uvicorn.run(_http_app(token), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
