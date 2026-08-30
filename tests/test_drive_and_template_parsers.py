"""
Unit tests for Google Drive & Google Docs template parsers, validation, and image normalization.
"""

import base64
import io
import re
import unittest
from pathlib import Path

from PIL import Image

from agents.receipt_scanner.docx_generator import calculate_receipt_totals, generate_expense_report_docx
from agents.receipt_scanner.tools import (
    REQUIRED_TEMPLATE_TAGS,
    _extract_text_from_gdoc,
    extract_google_doc_id,
    extract_google_drive_folder_id,
)


class TestGoogleDriveAndDocParsers(unittest.TestCase):
    """Tests URL parsing and ID extraction for Google Drive folders and Google Docs templates."""

    def test_extract_drive_folder_id_from_standard_url(self):
        url = "https://drive.google.com/drive/folders/1aBcDeFgHiJkLmNoPqRsTuVwXyZ"
        self.assertEqual(extract_google_drive_folder_id(url), "1aBcDeFgHiJkLmNoPqRsTuVwXyZ")

    def test_extract_drive_folder_id_with_user_index_and_query(self):
        url = "https://drive.google.com/drive/u/0/folders/1aBcDeFgHiJkLmNoPqRsTuVwXyZ?usp=sharing"
        self.assertEqual(extract_google_drive_folder_id(url), "1aBcDeFgHiJkLmNoPqRsTuVwXyZ")

    def test_extract_drive_folder_id_from_id_param(self):
        url = "https://drive.google.com/open?id=1aBcDeFgHiJkLmNoPqRsTuVwXyZ"
        self.assertEqual(extract_google_drive_folder_id(url), "1aBcDeFgHiJkLmNoPqRsTuVwXyZ")

    def test_extract_drive_folder_id_from_raw_id(self):
        raw_id = "1aBcDeFgHiJkLmNoPqRsTuVwXyZ_12345"
        self.assertEqual(extract_google_drive_folder_id(raw_id), raw_id)

    def test_extract_drive_folder_id_invalid_inputs(self):
        self.assertIsNone(extract_google_drive_folder_id(""))
        self.assertIsNone(extract_google_drive_folder_id(None))
        self.assertIsNone(extract_google_drive_folder_id("https://example.com/invalid/path"))
        self.assertIsNone(extract_google_drive_folder_id("short"))

    def test_extract_google_doc_id_from_standard_url(self):
        url = "https://docs.google.com/document/d/1nkT3N6ovmmBJYDK9S9oRRaOZ6sCQkAwve58y7sS2eOw/edit"
        self.assertEqual(extract_google_doc_id(url), "1nkT3N6ovmmBJYDK9S9oRRaOZ6sCQkAwve58y7sS2eOw")

    def test_extract_google_doc_id_with_preview_and_query(self):
        url = "https://docs.google.com/document/d/1nkT3N6ovmmBJYDK9S9oRRaOZ6sCQkAwve58y7sS2eOw/preview?tab=t.0"
        self.assertEqual(extract_google_doc_id(url), "1nkT3N6ovmmBJYDK9S9oRRaOZ6sCQkAwve58y7sS2eOw")

    def test_extract_google_doc_id_from_raw_id(self):
        raw_id = "1nkT3N6ovmmBJYDK9S9oRRaOZ6sCQkAwve58y7sS2eOw"
        self.assertEqual(extract_google_doc_id(raw_id), raw_id)

    def test_extract_google_doc_id_invalid_inputs(self):
        self.assertIsNone(extract_google_doc_id(""))
        self.assertIsNone(extract_google_doc_id(None))
        self.assertIsNone(extract_google_doc_id("https://drive.google.com/drive/folders/12345"))

    def test_export_summary_blocks_when_google_drive_folder_is_missing(self):
        from unittest.mock import patch

        from agents.receipt_scanner.tools import export_summary_to_google_doc

        with patch.dict("os.environ", {}, clear=True):
            res = export_summary_to_google_doc(
                title="Expense_Report",
                receipts_data=[{"original_amount": 10.0, "currency": "PLN", "desc": "Taxi"}],
            )
            self.assertFalse(res.get("success"))
            self.assertEqual(res.get("error"), "MISSING_GOOGLE_DRIVE_FOLDER")


class TestGoogleDocTemplateValidation(unittest.TestCase):
    """Tests structure extraction and placeholder validation for Google Docs templates."""

    def test_extract_text_from_nested_gdoc_structure(self):
        mock_gdoc = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "GDG Expense Report: {{TITLE}}\n"}},
                                {"textRun": {"content": "Date: {{Current date}}\n"}},
                            ]
                        }
                    },
                    {
                        "table": {
                            "tableRows": [
                                {
                                    "tableCells": [
                                        {
                                            "content": [
                                                {"paragraph": {"elements": [{"textRun": {"content": "{{Category}}"}}]}}
                                            ]
                                        },
                                        {
                                            "content": [
                                                {"paragraph": {"elements": [{"textRun": {"content": "{{Desc}}"}}]}}
                                            ]
                                        },
                                        {
                                            "content": [
                                                {"paragraph": {"elements": [{"textRun": {"content": "{{SUM CURR}}"}}]}}
                                            ]
                                        },
                                        {
                                            "content": [
                                                {
                                                    "paragraph": {
                                                        "elements": [{"textRun": {"content": "{{SUM EUR/USD}}"}}]
                                                    }
                                                }
                                            ]
                                        },
                                    ]
                                }
                            ]
                        }
                    },
                    {
                        "paragraph": {
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "Total: {{TOTAL SUM CURR}} (Converted: {{TOTAL SUM EUR/USD}})\n"
                                    }
                                }
                            ]
                        }
                    },
                ]
            }
        }
        text = _extract_text_from_gdoc(mock_gdoc)
        for tag in REQUIRED_TEMPLATE_TAGS:
            self.assertIn(tag, text, f"Expected tag {tag} to be found in extracted text")

    def test_detects_missing_template_tags(self):
        incomplete_gdoc = {
            "body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": "Expense Report {{TITLE}}\n"}}]}}]}
        }
        text = _extract_text_from_gdoc(incomplete_gdoc)
        missing = [tag for tag in REQUIRED_TEMPLATE_TAGS if tag not in text]
        self.assertGreater(len(missing), 0)
        self.assertIn("{{Current date}}", missing)
        self.assertIn("{{TOTAL SUM CURR}}", missing)


class TestDocxAndProofImageEmbedding(unittest.TestCase):
    """Tests image normalization and DOCX embedding without Proof # captions."""

    def setUp(self):
        # Create a simple test image in memory
        img = Image.new("RGB", (60, 60), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.sample_png_bytes = buf.getvalue()
        self.sample_base64 = base64.b64encode(self.sample_png_bytes).decode("utf-8")
        self.sample_data_url = f"data:image/png;base64,{self.sample_base64}"

    def test_generate_docx_with_base64_and_bytes(self):
        receipts_data = [
            {
                "category": "Transport",
                "desc": "Uber Taxi",
                "sum_curr": "45.00 PLN",
                "sum_target": "11.25 USD",
                "original_amount": 45.0,
                "currency": "PLN",
            }
        ]
        docx_bytes = generate_expense_report_docx(
            title="Test_Expense_Report",
            receipts_data=receipts_data,
            target_currency="USD",
            exchange_rate=4.0,
            rate_source="Test Pekao",
            session_images=[self.sample_base64, self.sample_png_bytes, self.sample_data_url],
        )
        self.assertIsNotNone(docx_bytes)
        self.assertGreater(len(docx_bytes), 1000)

    def test_generate_docx_with_rate_url(self):
        receipts_data = [
            {
                "category": "Transport",
                "desc": "Train Ticket",
                "sum_curr": "80.00 PLN",
                "sum_target": "20.00 USD",
                "original_amount": 80.0,
                "currency": "PLN",
            }
        ]
        docx_bytes = generate_expense_report_docx(
            title="Test_Expense_Report_URL",
            receipts_data=receipts_data,
            target_currency="USD",
            exchange_rate=4.0,
            rate_source="Pekao Bank kupuje USD/PLN",
            rate_url="https://www.pekao.com.pl/kursy-walut.html",
        )
        self.assertIsNotNone(docx_bytes)
        self.assertGreater(len(docx_bytes), 1000)

    def test_calculate_receipt_totals(self):
        receipts_data = [
            {"sum_curr": "100.00 PLN", "sum_target": "25.00 USD", "currency": "PLN"},
            {"sum_curr": "50.00 PLN", "sum_target": "12.50 USD", "currency": "PLN"},
        ]
        total_curr, total_target = calculate_receipt_totals(receipts_data, "USD")
        self.assertEqual(total_curr, "150.00 PLN")
        self.assertEqual(total_target, "37.50 USD")


class TestAgentInstructionsSafety(unittest.TestCase):
    """Verifies that no agent instruction contains unescaped curly brace template variables."""

    def test_no_unescaped_curly_variable_templates_in_agents(self):
        agents_dir = Path(__file__).parent.parent / "agents"
        agent_files = list(agents_dir.glob("*/agent.py"))
        self.assertGreater(len(agent_files), 0)

        for agent_file in agent_files:
            content = agent_file.read_text(encoding="utf-8")
            # Ensure there is no stray unescaped {N} or single letter template variable in instructions
            stray_matches = re.findall(r"\{\{?([A-Za-z])\}\}?", content)
            # Filter out standard f-string variables like {current_year}, {community_name}
            self.assertNotIn("N", stray_matches, f"Found unescaped '{{N}}' variable in {agent_file}")


if __name__ == "__main__":
    unittest.main()
