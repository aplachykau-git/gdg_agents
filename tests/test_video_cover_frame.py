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


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not installed")
class StandaloneCoverPosterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.orig_base_dir = composer_tools.BASE_DIR
        composer_tools.BASE_DIR = self.tmp
        os.makedirs(os.path.join(self.tmp, "assets"), exist_ok=True)
        os.makedirs(os.path.join(self.tmp, "snapshots"), exist_ok=True)
        with open(os.path.join(self.tmp, "index.html"), "w", encoding="utf-8") as f:
            f.write(
                '<html><head><style></style></head><body data-duration="10">'
                '<video id="card-video" src="assets/Video_example.mp4"></video>'
                '<img id="card-image" src="assets/staged_media.jpg">'
                '<span id="cursor"></span>'
                '<script>const CARD_CONFIG = { title: "Agents", name: "Jane Doe", position_company: "GDE" };</script>'
                "</body></html>"
            )

    def tearDown(self):
        composer_tools.BASE_DIR = self.orig_base_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_render_cover_poster_outputs_4k_png_even_when_render_4k_disabled(self):
        snapshot = os.path.join(self.tmp, "snapshots", "frame-00-at-9.7s.png")
        Image.new("RGB", (1920, 1080), (20, 80, 200)).save(snapshot)

        with (
            mock.patch.dict(os.environ, {"RENDER_4K": "false"}),
            mock.patch.object(composer_tools, "_capture_card_snapshot", return_value=snapshot),
            mock.patch.object(composer_tools, "upload_file_to_storage", return_value=None),
        ):
            summary = composer_tools.render_cover_poster()

        self.assertIn("High-Resolution Card Poster (4K PNG)", summary)
        poster_path = summary.split("High-Resolution Card Poster (4K PNG): ", 1)[1].strip()
        self.assertTrue(os.path.exists(poster_path))
        with Image.open(poster_path) as out_img:
            self.assertEqual(out_img.size, (3840, 2160))

    def test_capture_card_snapshot_skips_500x500_placeholder_avatar(self):
        composer_tools.restore_default_placeholder(force=True)
        Image.new("RGB", (600, 800), (10, 200, 30)).save(os.path.join(self.tmp, "assets", "staged_media.jpg"))
        captured_html = []

        def fake_run(cmd, *args, **kwargs):
            with open(os.path.join(self.tmp, "index.html"), "r", encoding="utf-8") as f:
                captured_html.append(f.read())
            snap = os.path.join(self.tmp, "snapshots", "frame-00-at-9.7s.png")
            Image.new("RGB", (1920, 1080), (10, 200, 30)).save(snap)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with mock.patch.object(composer_tools.subprocess, "run", side_effect=fake_run) as run_mock:
            snap = composer_tools._capture_card_snapshot(os.path.join(self.tmp, "index.html"), os.environ.copy(), True)

        self.assertIsNotNone(snap)
        self.assertIn('id="card-image" src="assets/staged_media.jpg"', captured_html[0])
        called_cmd = run_mock.call_args[0][0]
        self.assertIn("--no-end", called_cmd)
        self.assertIn(f"--output={os.path.join(self.tmp, 'snapshots')}", called_cmd)

    def test_capture_card_snapshot_finds_nested_hyperframes_artifacts_snapshot(self):
        Image.new("RGB", (600, 800), (10, 200, 30)).save(os.path.join(self.tmp, "assets", "staged_media.jpg"))
        nested_dir = os.path.join(self.tmp, ".hyperframes", "artifacts", "snapshots", "snap-abc123")

        def fake_run(cmd, *args, **kwargs):
            os.makedirs(nested_dir, exist_ok=True)
            snap = os.path.join(nested_dir, "at-9.7s.png")
            Image.new("RGB", (1920, 1080), (40, 120, 240)).save(snap)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        with mock.patch.object(composer_tools.subprocess, "run", side_effect=fake_run):
            snap = composer_tools._capture_card_snapshot(os.path.join(self.tmp, "index.html"), os.environ.copy(), True)

        self.assertEqual(snap, os.path.join(nested_dir, "at-9.7s.png"))
        composer_tools._cleanup_snapshot_artifacts()
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "snapshots")))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, ".hyperframes", "artifacts", "snapshots")))

    def test_normalize_title_text_handles_nbsp_and_nowrap_markers(self):
        self.assertEqual(
            composer_tools.normalize_title_text("How to do RAG in&nbsp;2027?"),
            "How to do RAG in\u00a02027?",
        )
        self.assertEqual(
            composer_tools.normalize_title_text("[[How to do RAG in 2027?]]"),
            "How\u00a0to\u00a0do\u00a0RAG\u00a0in\u00a02027?",
        )
        self.assertEqual(
            composer_tools.normalize_title_text("How to do RAG [[in 2027?]]"),
            "How to do RAG in\u00a02027?",
        )

    def test_outpaint_preserves_9_16_and_uses_anti_zoom_prompt(self):
        from agents.video_editor.tools import media_tools

        orig_media_base = media_tools.BASE_DIR
        media_tools.BASE_DIR = self.tmp
        try:
            tall_src = os.path.join(self.tmp, "assets", "already_9_16.png")
            Image.new("RGB", (768, 1376), (20, 40, 60)).save(tall_src)
            fake_client = mock.MagicMock()
            rel = media_tools.outpaint_to_9_16(tall_src, fake_client)
            self.assertEqual(rel, "assets/portrait_outpainted.png")
            fake_client.models.generate_content.assert_not_called()

            wide_src = os.path.join(self.tmp, "assets", "square.png")
            Image.new("RGB", (800, 800), (20, 40, 60)).save(wide_src)
            fake_client.models.generate_content.return_value = mock.MagicMock(candidates=[])
            media_tools.outpaint_to_9_16(wide_src, fake_client)
            prompt_text = fake_client.models.generate_content.call_args.kwargs["contents"][1].text
            self.assertIn("DO NOT zoom out or shrink the person", prompt_text)
            self.assertIn("DO NOT invent legs", prompt_text)
        finally:
            media_tools.BASE_DIR = orig_media_base


if __name__ == "__main__":
    unittest.main()
