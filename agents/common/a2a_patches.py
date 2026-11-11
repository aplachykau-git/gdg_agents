"""A2A protocol compatibility patches for reliable Server-Sent Events (SSE) streaming.

Fixes a known incompatibility where `httpx.Response.aiter_lines()` uses Python's
`str.splitlines()` (which splits on Unicode line/paragraph separators \\u2028, \\u2029,
\\x0b, \\x0c, \\x85, etc.). In W3C SSE, lines are strictly delimited ONLY by CRLF, LF,
or CR. When an agent returns JSON payloads containing \\u2028 (common in copied text,
PDFs, LinkedIn bios), `aiter_lines()` breaks the JSON line, causing:
"A2A request failed: Unterminated string starting at: line 1 column X (char Y)".
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, AsyncGenerator

if TYPE_CHECKING:
    import httpx

logger = logging.getLogger(__name__)

_PATCHED = False


async def robust_parse_sse_stream(
    response: httpx.Response,
) -> AsyncGenerator[tuple[str, str], None]:
    """Yields (event_name, data) from a streaming httpx.Response.

    Conforms strictly to the W3C Server-Sent Events specification by splitting
    lines only on \\r\\n, \\n, or \\r. Unlike `httpx.Response.aiter_lines()`, this
    never treats Unicode characters (\\u2028 Line Separator, \\u2029 Paragraph Separator,
    \\x0b, \\x0c, \\x85) as SSE line boundaries.
    """
    event_name = "message"
    payload_chunks: list[str] = []
    buffer = ""

    async for chunk in response.aiter_text():
        buffer += chunk
        while True:
            r_pos = buffer.find("\r")
            n_pos = buffer.find("\n")

            if r_pos != -1 and (n_pos == -1 or r_pos < n_pos):
                if r_pos + 1 < len(buffer):
                    if buffer[r_pos + 1] == "\n":
                        nl_pos = r_pos
                        nl_len = 2
                    else:
                        nl_pos = r_pos
                        nl_len = 1
                else:
                    # Trailing \r at the very end of chunk; wait for next chunk
                    # to disambiguate CRLF from bare CR.
                    break
            elif n_pos != -1:
                nl_pos = n_pos
                nl_len = 1
            else:
                break

            line = buffer[:nl_pos]
            buffer = buffer[nl_pos + nl_len :]

            # Empty line denotes the completion of the current event block
            if not line:
                if payload_chunks:
                    yield event_name, "\n".join(payload_chunks)
                event_name = "message"
                payload_chunks = []
                continue

            # Ignore comment lines
            if line.startswith(":"):
                continue

            # Split key and value by first colon
            parts = line.split(":", 1)
            key = parts[0]
            val = parts[1] if len(parts) > 1 else ""

            # Strip a single optional leading space
            if val.startswith(" "):
                val = val[1:]

            if key == "event":
                event_name = val
            elif key == "data":
                payload_chunks.append(val)

    # Flush any remaining buffer at stream end
    if buffer:
        line = buffer.rstrip("\r\n")
        if line and not line.startswith(":"):
            parts = line.split(":", 1)
            key = parts[0]
            val = parts[1] if len(parts) > 1 else ""
            if val.startswith(" "):
                val = val[1:]
            if key == "event":
                event_name = val
            elif key == "data":
                payload_chunks.append(val)

    if payload_chunks:
        yield event_name, "\n".join(payload_chunks)


def apply_a2a_patches() -> None:
    """Applies runtime monkey patches to A2A SDK transports and JSON serialization."""
    global _PATCHED
    if _PATCHED:
        return

    patched_items = []

    # 1. Patch SSE parser on A2A client side
    try:
        import a2a.client.transports.http_helpers as http_helpers

        http_helpers.parse_sse_stream = robust_parse_sse_stream
        patched_items.append("a2a.client.transports.http_helpers.parse_sse_stream")
    except (ImportError, AttributeError):
        pass

    # 2. Patch JSON serializer on A2A server side so \u2028/\u2029 are escaped for unpatched clients
    try:
        import a2a.utils.json_utils as a2a_json_utils

        _orig_dumps = a2a_json_utils.dumps

        def _safe_dumps(obj: Any) -> str:
            serialized = _orig_dumps(obj)
            if "\u2028" in serialized or "\u2029" in serialized:
                return serialized.replace("\u2028", r"\u2028").replace("\u2029", r"\u2029")
            return serialized

        a2a_json_utils.dumps = _safe_dumps
        patched_items.append("a2a.utils.json_utils.dumps")
    except (ImportError, AttributeError):
        pass

    _PATCHED = True
    if patched_items:
        logger.debug("Applied A2A SSE compatibility patches: %s", ", ".join(patched_items))
