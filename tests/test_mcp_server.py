"""The MCP server, exercised through a real in-process MCP client (offline: no Gemini/Omni)."""

import asyncio
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

with patch.dict(os.environ, {"LOG_STREAM": "stderr"}):
    from agents import mcp_server

from mcp import Client

PHOTO = Path(__file__).resolve().parent.parent / "agents" / "video_editor" / "assets" / "portrait_outpainted.png"
SPEAKER = {"talk_title": "Agents in Production", "name": "Jane Doe", "position_company": "GDE, Example"}


def payload(result) -> dict:
    if getattr(result, "structured_content", None):
        return result.structured_content
    return json.loads(result.content[0].text)


class TestMcpServer(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {"VIDEO_EDITOR_OFFLINE": "true"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_client(self, scenario):
        async def main():
            async with Client(mcp_server.mcp) as client:
                return await scenario(client)

        return asyncio.run(main())

    def test_lists_the_studio_tools(self):
        async def scenario(client):
            return {tool.name for tool in (await client.list_tools()).tools}

        self.assertEqual(
            self.run_client(scenario),
            {
                "propose_video_scenarios",
                "start_speaker_card_render",
                "get_render_status",
                "process_registration_list",
                "scan_receipt",
                "generate_qr_code",
            },
        )

    def test_scenarios_then_render_job(self):
        async def scenario(client):
            proposed = payload(await client.call_tool("propose_video_scenarios", SPEAKER))
            option = proposed["scenarios"][1]
            started = payload(
                await client.call_tool(
                    "start_speaker_card_render",
                    {**SPEAKER, "photo": str(PHOTO), "creative_direction": option["styles"][0]["creative_direction"]},
                )
            )
            for _ in range(50):
                status = payload(await client.call_tool("get_render_status", {"job_id": started["job_id"]}))
                if status["status"] != "running":
                    break
                await asyncio.sleep(0.05)
            return proposed, status

        proposed, status = self.run_client(scenario)
        self.assertEqual(len(proposed["scenarios"]), 5)
        self.assertTrue(all(sc["styles"] and sc["creative_direction"] for sc in proposed["scenarios"]))
        self.assertEqual(status["status"], "done")
        self.assertTrue(status["urls"]["video"].endswith("Video_example.mp4"))

    def test_unknown_job(self):
        async def scenario(client):
            return payload(await client.call_tool("get_render_status", {"job_id": "nope"}))

        self.assertEqual(self.run_client(scenario)["status"], "unknown")

    def test_missing_photo_fails_cleanly_outside_offline_mode(self):
        async def scenario(client):
            started = payload(
                await client.call_tool(
                    "start_speaker_card_render",
                    {**SPEAKER, "photo": "/nonexistent/photo.png", "creative_direction": "x"},
                )
            )
            for _ in range(50):
                status = payload(await client.call_tool("get_render_status", {"job_id": started["job_id"]}))
                if status["status"] != "running":
                    return status
                await asyncio.sleep(0.05)
            return status

        async def no_review(metadata):
            return None

        with (
            patch.dict(os.environ, {"VIDEO_EDITOR_OFFLINE": "false"}),
            patch.object(mcp_server.cards, "_review_metadata", side_effect=no_review),
            patch.object(mcp_server.cards.workflow, "validate_render_environment", return_value=None),
        ):
            status = self.run_client(scenario)
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["code"], "media_not_found")


class TestMcpQrCode(TestMcpServer):
    def test_generate_qr_code_writes_svg_and_png(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:

            async def scenario(client):
                return payload(await client.call_tool("generate_qr_code", {"link": "gdg.dev", "output_dir": tmp}))

            result = self.run_client(scenario)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["link"], "https://gdg.dev")
            self.assertTrue(Path(result["svg"]).read_text().startswith("<svg"))
            self.assertTrue(Path(result["png"]).read_bytes().startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
