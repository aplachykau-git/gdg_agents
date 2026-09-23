"""Sessions must survive a service restart (new Runner / new process) when stored in a database."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.common import runtime
from agents.video_editor.agent import video_editor_agent
from tests.agent_harness import AgentHarness, call, text

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452")
SPEAKER = {"talk_title": "Agents in Production", "name": "Jane Doe", "position_company": "GDE, Example"}


class TestSessionServiceSelection(unittest.TestCase):
    def test_uri_from_environment_wins(self):
        with patch.dict(os.environ, {"SESSION_SERVICE_URI": "memory://"}):
            service = runtime.build_session_service("video_editor")
        self.assertEqual(type(service).__name__, "InMemorySessionService")

    def test_local_default_is_a_sqlite_file(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(runtime, "AGENTS_ROOT", Path(tmp)),
            patch.dict(os.environ, {"SESSION_SERVICE_URI": ""}),
        ):
            service = runtime.build_session_service("video_editor")
            self.assertEqual(type(service).__name__, "SqliteSessionService")
            self.assertTrue((Path(tmp) / "video_editor" / ".adk").is_dir())

    def test_password_is_redacted_in_logs(self):
        self.assertEqual(
            runtime._redact("postgresql+asyncpg://adk:secret@/db?host=/cloudsql/x"),
            "postgresql+asyncpg://***@/db?host=/cloudsql/x",
        )


class TestCardSurvivesRestart(unittest.TestCase):
    def test_video_card_is_restored_by_a_fresh_runner(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(
                os.environ, {"VIDEO_EDITOR_OFFLINE": "true", "SESSION_SERVICE_URI": f"sqlite:///{tmp}/sessions.db"}
            ),
        ):
            first = AgentHarness(video_editor_agent, session_service=runtime.build_session_service("video_editor"))
            first.script(
                call("update_speaker", **SPEAKER), text("Saved."), call("propose_scenarios"), text("Pick one.")
            )
            first.say("Card please", attachments=[("image/png", PNG)])
            first.say("Ideas?")

            # "restart": brand-new service objects pointing at the same database
            second = AgentHarness(
                video_editor_agent,
                session_service=runtime.build_session_service("video_editor"),
                session_id=first.session_id,
            )
            second.script(call("render_video", option="2"), text("Done."))
            events = second.say("Render option 2")
            renders = second.state()["video_editor_session"]["renders"]

        rendered = AgentHarness.tool_responses(events, "render_video")
        self.assertEqual(rendered[0]["status"], "success")
        self.assertEqual(rendered[0]["speaker"]["name"], "Jane Doe")
        self.assertEqual(len(renders), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
