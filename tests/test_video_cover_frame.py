"""Cover frame: the first video frame shows the finished card instead of an empty canvas."""

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from PIL import Image

from agents.video_editor.tools import composer_tools

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _make_video(path: str, seconds: float = 1.0, color: str = "black") -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:size=320x180:rate=30",
            "-t",
            str(seconds),
            "-pix_fmt",
            "yuv420p",
            path,
        ],
        check=True,
    )


def _frame_count(path: str) -> int:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(out.stdout.strip())


def _frame_rgb(path: str, index: int, out_png: str) -> tuple[int, int, int]:
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-i",
            path,
            "-vf",
            f"select=eq(n\\,{index})",
            "-frames:v",
            "1",
            out_png,
        ],
        check=True,
    )
    with Image.open(out_png) as img:
        return img.convert("RGB").getpixel((img.width // 2, img.height // 2))


class CoverFrameSettingsTests(unittest.TestCase):
    def test_enabled_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VIDEO_COVER_FRAME", None)
            self.assertTrue(composer_tools.cover_frame_enabled())

    def test_can_be_disabled(self):
        for value in ("false", "0", "off", "NO"):
            with mock.patch.dict(os.environ, {"VIDEO_COVER_FRAME": value}):
                self.assertFalse(composer_tools.cover_frame_enabled())

    def test_seconds_default_and_invalid(self):
        with mock.patch.dict(os.environ, {"VIDEO_COVER_SECONDS": "abc"}):
            self.assertEqual(composer_tools.cover_frame_seconds(), 0.0)
        with mock.patch.dict(os.environ, {"VIDEO_COVER_SECONDS": "0.5"}):
            self.assertEqual(composer_tools.cover_frame_seconds(), 0.5)

    def test_missing_files_leave_video_untouched(self):
        self.assertFalse(composer_tools.prepend_cover_frame("/nonexistent.mp4", "/nonexistent.png"))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not installed")
class PrependCoverFrameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.video = os.path.join(self.tmp, "card.mp4")
        self.cover = os.path.join(self.tmp, "cover.png")
        _make_video(self.video, seconds=1.0, color="black")
        # Different aspect ratio on purpose: the cover must be fitted, not stretched or rejected.
        Image.new("RGB", (640, 400), (240, 40, 40)).save(self.cover)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_frame_is_the_cover_and_one_frame_is_added(self):
        before = _frame_count(self.video)
        self.assertTrue(composer_tools.prepend_cover_frame(self.video, self.cover))
        self.assertEqual(_frame_count(self.video), before + 1)

        r, g, b = _frame_rgb(self.video, 0, os.path.join(self.tmp, "f0.png"))
        self.assertGreater(r, 180)
        self.assertLess(g, 90)
        r, g, b = _frame_rgb(self.video, 1, os.path.join(self.tmp, "f1.png"))
        self.assertLess(max(r, g, b), 40)

    def test_keeps_resolution(self):
        composer_tools.prepend_cover_frame(self.video, self.cover)
        self.assertEqual(composer_tools._probe_video(self.video)[:2], (320, 180))

    def test_longer_hold(self):
        before = _frame_count(self.video)
        composer_tools.prepend_cover_frame(self.video, self.cover, seconds=0.5)
        self.assertEqual(_frame_count(self.video), before + 15)

    def test_ffmpeg_failure_keeps_original(self):
        with open(self.video, "rb") as f:
            original = f.read()
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="boom")
        real_run = subprocess.run

        def fake_run(cmd, *args, **kwargs):
            if cmd and cmd[0] == "ffmpeg":
                return failed
            return real_run(cmd, *args, **kwargs)

        with mock.patch.object(composer_tools.subprocess, "run", side_effect=fake_run):
            self.assertFalse(composer_tools.prepend_cover_frame(self.video, self.cover))
        with open(self.video, "rb") as f:
            self.assertEqual(f.read(), original)


if __name__ == "__main__":
    unittest.main()
