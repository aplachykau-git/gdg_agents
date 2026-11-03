"""QR code generator: rounded flat SVG + PNG that phones can actually scan."""

import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from agents.qr_code_generator import tools as qr_tools
from agents.qr_code_generator.agent import qr_agent
from agents.qr_code_generator.qr_render import QrStyle, build_qr, normalize_link
from tests.agent_harness import AgentHarness, call, text

try:
    import zxingcpp
except ImportError:  # decoder is a dev-only dependency
    zxingcpp = None

LINK = "https://gdg.community.dev/gdg-krakow/"


def decode(png: bytes) -> list[str]:
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    flat = Image.new("RGBA", image.size, "white")
    flat.alpha_composite(image)
    return [barcode.text for barcode in zxingcpp.read_barcodes(flat)]


class TestNormalizeLink(unittest.TestCase):
    def test_adds_https_to_bare_domains(self):
        self.assertEqual(normalize_link(" gdg.community.dev/gdg-krakow "), "https://gdg.community.dev/gdg-krakow")
        self.assertEqual(normalize_link("www.example.com"), "https://www.example.com")
        self.assertEqual(normalize_link("<https://a.io/x>"), "https://a.io/x")

    def test_keeps_other_schemes_and_text(self):
        self.assertEqual(normalize_link("mailto:hi@gdg.dev"), "mailto:hi@gdg.dev")
        self.assertEqual(normalize_link("http://localhost:8080"), "http://localhost:8080")
        self.assertEqual(normalize_link("Hello world"), "Hello world")

    def test_rejects_empty_and_huge(self):
        with self.assertRaises(ValueError):
            normalize_link("   ")
        with self.assertRaises(ValueError):
            normalize_link("https://x.io/" + "a" * 3000)


class TestRender(unittest.TestCase):
    def test_svg_is_one_flat_path(self):
        svg = build_qr(LINK).svg
        self.assertEqual(svg.count("<path"), 1)
        self.assertNotIn("<image", svg)
        self.assertNotIn("Gradient", svg)
        self.assertIn(" A", svg.replace("A", " A"))  # rounded corners are arcs
        self.assertRegex(svg, r'viewBox="0 0 (\d+) \1"')

    def test_separate_eye_colour_adds_second_path(self):
        svg = build_qr(LINK, QrStyle(color="#1A73E8", eye_color="#EA4335")).svg
        self.assertEqual(svg.count("<path"), 2)
        self.assertIn('fill="#EA4335"', svg)

    def test_transparent_has_no_background(self):
        result = build_qr(LINK, QrStyle(transparent=True))
        self.assertNotIn("<rect", result.svg)
        image = Image.open(io.BytesIO(result.png)).convert("RGBA")
        self.assertEqual(image.getpixel((2, 2))[3], 0)

    def test_png_size(self):
        png = build_qr(LINK, png_size=512).png
        self.assertEqual(Image.open(io.BytesIO(png)).size, (512, 512))

    def test_rejects_bad_colours(self):
        with self.assertRaises(ValueError):
            build_qr(LINK, QrStyle(color="blue"))

    @unittest.skipIf(zxingcpp is None, "zxing-cpp not installed")
    def test_png_scans(self):
        long_link = "https://example.com/register?utm_source=linkedin&utm_campaign=devfest-2026&ref=gdg-krakow"
        for link, style in [
            (LINK, QrStyle()),
            (long_link, QrStyle(color="#1A73E8", eye_color="#EA4335")),
            (LINK, QrStyle(transparent=True, color="#202124")),
        ]:
            with self.subTest(link=link, style=style):
                self.assertEqual(decode(build_qr(link, style).png), [link])


class TestTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # save_qr binds RESULTS_DIR as a default argument at import time
        patcher = patch.object(qr_tools.save_qr, "__defaults__", (Path(self.tmp.name),))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_success_returns_card_and_files(self):
        with patch.dict("os.environ", {"GCS_BUCKET_NAME": "", "K_SERVICE": ""}):
            result = qr_tools.generate_qr_code("gdg.community.dev/gdg-krakow/", color="#1A73E8")
        self.assertEqual(result["status"], "success")
        ui = result["ui"]
        self.assertEqual(ui["type"], "qr_code")
        self.assertEqual(ui["link"], LINK)
        self.assertRegex(ui["svg_url"], r"^/results/qr_gdg-community-dev-gdg-krakow_[0-9a-f]{8}\.svg$")
        self.assertTrue(ui["png_url"].endswith(".png"))
        files = sorted(p.suffix for p in Path(self.tmp.name).iterdir())
        self.assertEqual(files, [".png", ".svg"])
        self.assertNotIn("<svg", str(result))  # the model never sees the file contents

    def test_error_is_reported(self):
        result = qr_tools.generate_qr_code("https://ok.dev", color="not-a-colour")
        self.assertEqual(result["status"], "error")
        self.assertIn("hex colour", result["message"])


class TestAgent(unittest.TestCase):
    def test_agent_calls_the_tool_and_shows_the_card(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(qr_tools.save_qr, "__defaults__", (Path(tmp),)):
            harness = AgentHarness(qr_agent).script(
                call("generate_qr_code", link="https://gdg.dev/join"),
                text("QR code is ready."),
            )
            events = harness.say("Make a QR for https://gdg.dev/join")
        responses = [
            part.function_response.response
            for event in events
            for part in (event.content.parts if event.content else [])
            if part.function_response
        ]
        self.assertEqual(responses[0]["ui"]["type"], "qr_code")
        self.assertTrue(re.match(r"^/results/qr_gdg-dev-join_", responses[0]["svg_url"]))


if __name__ == "__main__":
    unittest.main()
