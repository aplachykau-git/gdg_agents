"""Unit tests for A2A Server-Sent Events (SSE) streaming parser and patches."""

import asyncio
import json
import unittest
from typing import AsyncGenerator

from agents.common.a2a_patches import apply_a2a_patches, robust_parse_sse_stream


class MockHttpxResponse:
    """Mock for httpx.Response providing aiter_text."""

    def __init__(self, chunks: list[str]):
        self._chunks = chunks

    async def aiter_text(self) -> AsyncGenerator[str, None]:
        for chunk in self._chunks:
            yield chunk


class TestA2aSseParser(unittest.IsolatedAsyncioTestCase):
    """Verifies that the robust SSE parser adheres to W3C SSE standard and handles edge cases."""

    async def test_unicode_line_separator_in_json_is_not_split(self):
        """\\u2028 and \\u2029 inside JSON data must not break the SSE data line."""
        json_payload = json.dumps(
            {
                "speaker": "Hubert Miś\u2028Staff Software Engineer, Google",
                "bio": "First paragraph\u2029Second paragraph",
            },
            ensure_ascii=False,
        )
        sse_text = f"data: {json_payload}\n\n"
        response = MockHttpxResponse([sse_text])

        events = [event async for event in robust_parse_sse_stream(response)]
        self.assertEqual(len(events), 1)
        event_name, data = events[0]
        self.assertEqual(event_name, "message")

        parsed = json.loads(data)
        self.assertEqual(parsed["speaker"], "Hubert Miś\u2028Staff Software Engineer, Google")
        self.assertEqual(parsed["bio"], "First paragraph\u2029Second paragraph")

    async def test_crlf_and_lf_and_cr_line_endings(self):
        """W3C SSE allows \\r\\n, \\n, and \\r line separators."""
        # Mix of \r\n, \n, and bare \r
        chunks = [
            "data: event_crlf\r\n\r\n",
            "data: event_lf\n\n",
            "data: event_cr\r\r",
        ]
        response = MockHttpxResponse(chunks)

        events = [event async for event in robust_parse_sse_stream(response)]
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0][1], "event_crlf")
        self.assertEqual(events[1][1], "event_lf")
        self.assertEqual(events[2][1], "event_cr")

    async def test_chunk_split_across_crlf(self):
        """A chunk boundary splitting \\r and \\n must be correctly handled as a single newline."""
        chunks = [
            "data: chunked_message\r",
            "\n\n",
        ]
        response = MockHttpxResponse(chunks)

        events = [event async for event in robust_parse_sse_stream(response)]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][1], "chunked_message")

    async def test_multiple_data_lines_in_single_event(self):
        """Multiple data lines within one event are joined by \\n according to SSE spec."""
        chunks = ["event: custom\ndata: line one\ndata: line two\n\n"]
        response = MockHttpxResponse(chunks)

        events = [event async for event in robust_parse_sse_stream(response)]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "custom")
        self.assertEqual(events[0][1], "line one\nline two")

    async def test_ignores_comment_lines(self):
        """Comment lines starting with ':' should be ignored."""
        chunks = [": ping heartbeat\ndata: actual payload\n\n: another comment\n"]
        response = MockHttpxResponse(chunks)

        events = [event async for event in robust_parse_sse_stream(response)]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][1], "actual payload")

    def test_apply_a2a_patches_installs_into_transport(self):
        """apply_a2a_patches monkey-patches parse_sse_stream in a2a.client.transports.http_helpers."""
        apply_a2a_patches()
        import a2a.client.transports.http_helpers as http_helpers

        self.assertIs(http_helpers.parse_sse_stream, robust_parse_sse_stream)


if __name__ == "__main__":
    unittest.main()
