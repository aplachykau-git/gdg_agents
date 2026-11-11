"""Receipt recognition summary: deterministic totals, conversion, budget and copy text."""

import unittest
from unittest import mock

from agents.common.event_series import community_currency_from_state
from agents.receipt_scanner import docx_generator, tools
from agents.receipt_scanner.summary import (
    _num,
    build_receipt_summary,
    group_and_sort_receipts,
    normalize_currency_code,
    parse_budget,
)

RATES = {"PLN": 1.0, "USD": 4.0, "EUR": 4.3, "GBP": 5.1, "CHF": 4.5}


def rate(code):
    return RATES[code]


KAUFLAND = {
    "merchant": "Kaufland",
    "desc": "Kaufland Grocery",
    "date": "2026-10-09",
    "category": "Food & drinks",
    "currency": "pln",
    "total": "124,50",
    "tax": 9.2,
    "items": [
        {"name": "Water", "quantity": 6, "unit_price": 2.5},
        {"name": "Pizza", "quantity": 1, "unit_price": 109.5, "total": 109.5},
    ],
}
UBER = {"merchant": "Uber", "date": "2026-10-10", "category": "taxi", "currency": "EUR", "total": 20}


class NumberParsingTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(_num("124,50"), 124.5)
        self.assertEqual(_num("1 234,50 zł"), 1234.5)
        self.assertEqual(_num("1,234.50"), 1234.5)
        self.assertEqual(_num("1.234,50"), 1234.5)
        self.assertEqual(_num("1,234"), 1234.0)
        self.assertEqual(_num(12), 12.0)
        self.assertIsNone(_num(""))
        self.assertIsNone(_num(None))
        self.assertIsNone(_num("n/a"))

    def test_budget(self):
        self.assertEqual(parse_budget("500 EUR"), (500.0, "EUR"))
        self.assertEqual(parse_budget("usd 1 200,50"), (1200.5, "USD"))
        self.assertEqual(parse_budget("300"), (300.0, ""))
        self.assertIsNone(parse_budget(""))


class BuildSummaryTests(unittest.TestCase):
    def test_same_currency_needs_no_rates(self):
        summary = build_receipt_summary([KAUFLAND], "PLN", rate_to_pln=None)
        row = summary["receipts"][0]
        self.assertEqual(row["currency"], "PLN")
        self.assertEqual(row["total"], 124.5)
        self.assertEqual(row["items"][0]["total"], 15.0)  # quantity x unit price
        self.assertEqual(row["items_sum"], 124.5)
        self.assertEqual(row["warnings"], [])
        self.assertEqual(summary["grand_total"], 124.5)
        self.assertEqual(summary["rates"], [])
        self.assertEqual(summary["conversion_note"], "")

    def test_conversion_categories_and_budget(self):
        summary = build_receipt_summary([KAUFLAND, UBER], "USD", "100 USD", rate_to_pln=rate)
        self.assertEqual(summary["target_currency"], "USD")
        self.assertEqual([r["total_target"] for r in summary["receipts"]], [31.12, 21.5])
        self.assertEqual(summary["grand_total"], 52.62)
        self.assertEqual(summary["receipts"][1]["category"], "Transport")
        self.assertEqual(summary["totals_by_category"][0], {"category": "Food & drinks", "amount": 31.12})
        self.assertEqual(
            summary["totals_by_currency"], [{"currency": "EUR", "amount": 20.0}, {"currency": "PLN", "amount": 124.5}]
        )
        self.assertEqual(summary["budget"]["remaining"], 47.38)
        self.assertFalse(summary["budget"]["over_budget"])

    def test_budget_in_other_currency_is_converted(self):
        summary = build_receipt_summary([KAUFLAND], "PLN", "10 USD", rate_to_pln=rate)
        self.assertEqual(summary["budget"]["amount"], 40.0)
        self.assertTrue(summary["budget"]["over_budget"])
        self.assertIn("over budget by", summary["text"])

    def test_target_defaults_to_budget_then_majority_currency(self):
        self.assertEqual(build_receipt_summary([KAUFLAND], "", "50 EUR", rate_to_pln=rate)["target_currency"], "EUR")
        self.assertEqual(
            build_receipt_summary([KAUFLAND, UBER, KAUFLAND], "", rate_to_pln=rate)["target_currency"], "PLN"
        )

    def test_items_not_adding_up_are_flagged(self):
        receipt = {**KAUFLAND, "total": 130}
        row = build_receipt_summary([receipt], "PLN")["receipts"][0]
        self.assertEqual(len(row["warnings"]), 1)
        self.assertIn("add up", row["warnings"][0])

    def test_unreadable_values_stay_empty(self):
        summary = build_receipt_summary([{"merchant": "Blurry", "notes": ["Bottom of the receipt is torn"]}], "PLN")
        row = summary["receipts"][0]
        self.assertIsNone(row["total"])
        self.assertIsNone(summary["grand_total"])
        self.assertEqual(len(row["warnings"]), 3)

    def test_rate_failure_keeps_original_amounts(self):
        def broken(code):
            raise RuntimeError("offline")

        summary = build_receipt_summary([KAUFLAND, UBER], "USD", rate_to_pln=broken)
        self.assertIsNone(summary["grand_total"])
        self.assertIsNone(summary["receipts"][0]["total_target"])
        self.assertIn("Could not get exchange rates", summary["conversion_note"])
        self.assertIn("124.50 PLN", summary["text"])

    def test_text_lists_items_and_totals(self):
        text = build_receipt_summary([KAUFLAND, UBER], "USD", rate_to_pln=rate)["text"]
        self.assertIn("1. Kaufland (2026-10-09 · Food & drinks)", text)
        self.assertIn("Water: 6 × 2.50 PLN = 15.00 PLN", text)
        self.assertIn("Total: 20.00 EUR (≈ 21.50 USD)", text)
        self.assertIn("Grand total: 52.62 USD", text)

    def test_ignores_garbage_rows(self):
        summary = build_receipt_summary([None, "x", KAUFLAND], "PLN")
        self.assertEqual(len(summary["receipts"]), 1)

    def test_converts_gbp_and_other_currencies_to_community_currency(self):
        gbp_receipt = {
            "merchant": "TfL London",
            "date": "2026-10-11",
            "category": "Transport",
            "currency": "£",
            "total": 20,
        }
        summary = build_receipt_summary(
            [KAUFLAND, UBER, gbp_receipt],
            "USD",
            rate_to_pln=rate,
            community_currency="PLN",
        )
        self.assertEqual(summary["receipts"][2]["currency"], "GBP")
        self.assertEqual(summary["receipts"][2]["total_community"], 102.0)
        self.assertEqual(summary["receipts"][2]["total_target"], 25.5)
        self.assertEqual(summary["community_currency"], "PLN")
        # 124.50 PLN + (20 EUR * 4.3 = 86.00 PLN) + (20 GBP * 5.1 = 102.00 PLN) = 312.50 PLN
        self.assertEqual(summary["community_total"], 312.5)
        self.assertIn("Community total (PLN): 312.50 PLN", summary["text"])

    def test_community_currency_resolution_and_normalization(self):
        self.assertEqual(normalize_currency_code("£"), "GBP")
        self.assertEqual(normalize_currency_code("pounds"), "GBP")
        self.assertEqual(normalize_currency_code("zł"), "PLN")
        self.assertEqual(community_currency_from_state({"community_name": "GDG Krakow"}), "PLN")
        self.assertEqual(community_currency_from_state({"community_name": "GDG London"}), "GBP")
        self.assertEqual(community_currency_from_state({"community_name": "GDG Berlin"}), "EUR")
        self.assertEqual(community_currency_from_state({"community_name": "GDG Prague"}), "CZK")


class ShowReceiptSummaryToolTests(unittest.TestCase):
    def test_returns_ui_payload(self):
        with mock.patch.object(tools, "get_nbp_rate", side_effect=rate):
            result = tools.show_receipt_summary([KAUFLAND, UBER], "USD", "")
        self.assertTrue(result["success"])
        self.assertEqual(result["ui"]["type"], "receipt_summary")
        self.assertEqual(result["grand_total"], 52.62)
        self.assertEqual(result["community_currency"], "PLN")
        self.assertEqual(result["community_total"], 210.5)
        self.assertIn("text", result["ui"])

    def test_get_exchange_rate_tool_for_gbp(self):
        with mock.patch.object(
            tools,
            "fetch_public_rate_to_pln",
            side_effect=lambda c: {"success": True, "rate": RATES[c], "source": "Public API", "url": ""},
        ):
            res = tools.get_exchange_rate("GBP", "PLN")
        self.assertTrue(res["success"])
        self.assertEqual(res["currency"], "GBP")
        self.assertEqual(res["target_currency"], "PLN")
        self.assertEqual(res["rate"], 5.1)

    def test_agent_exposes_tool(self):
        from agents.receipt_scanner.agent import receipt_agent

        names = [getattr(t, "__name__", "") for t in receipt_agent.tools]
        self.assertIn("show_receipt_summary", names)
        self.assertIn("get_exchange_rate", names)
        self.assertLess(names.index("show_receipt_summary"), names.index("export_summary_to_google_doc"))


class ReceiptProofCompressionTests(unittest.TestCase):
    def test_deduplicates_and_downscales_large_images(self):
        import io

        from PIL import Image

        from agents.receipt_scanner.docx_generator import (
            deduplicate_and_compress_proofs,
            generate_expense_report_docx,
        )

        # Create two distinct large images (2400x3200) and one duplicate
        images = []
        for color in ((240, 240, 240), (220, 235, 250)):
            img = Image.new("RGB", (2400, 3200), color=color)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            images.append(buf.getvalue())

        compressed = deduplicate_and_compress_proofs([images[0], images[1], images[0]])
        self.assertEqual(len(compressed), 2)
        for comp_bytes in compressed:
            out_img = Image.open(io.BytesIO(comp_bytes))
            self.assertLessEqual(max(out_img.size), 1350)
            self.assertEqual(out_img.format, "JPEG")

        # Verify DOCX generation with 6 unique receipts creates a compact grid table
        six_images = []
        for idx in range(6):
            img = Image.new("RGB", (1800, 2400), color=(200 + idx * 5, 210, 220))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=92)
            six_images.append(buf.getvalue())

        docx_bytes = generate_expense_report_docx(
            title="Test Compact Report",
            receipts_data=[
                {"category": "Venue", "desc": f"Item {i}", "sum_curr": "100.00 PLN", "sum_target": "25.00 USD"}
                for i in range(1, 7)
            ],
            target_currency="USD",
            session_images=six_images,
        )
        self.assertLess(len(docx_bytes), 300_000)

    def test_landscape_photo_with_vertical_text_lines_is_rotated_to_portrait(self):
        import io

        from PIL import Image, ImageDraw

        from agents.receipt_scanner.docx_generator import compress_receipt_image

        # Create a 1200x800 (width > height) photo simulating a sideways vertical receipt
        # where printed text lines run vertically (columns of dark stripes)
        img = Image.new("RGB", (1200, 800), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        for x in range(80, 1120, 28):
            draw.rectangle([x, 60, x + 8, 740], fill=(20, 20, 20))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)

        comp = compress_receipt_image(buf.getvalue(), auto_orient=True, use_vision_model=False)
        out_img = Image.open(io.BytesIO(comp))
        # Should be rotated into portrait orientation (height > width)
        self.assertGreater(out_img.size[1], out_img.size[0])

    def test_multipage_pdf_stitches_all_pages_vertically_into_single_proof(self):
        import io

        from PIL import Image

        from agents.receipt_scanner.docx_generator import compress_receipt_image

        # Create a 3-page PDF using PIL's multi-frame PDF writer
        page_1 = Image.new("RGB", (600, 800), color=(255, 220, 220))
        page_2 = Image.new("RGB", (600, 800), color=(220, 255, 220))
        page_3 = Image.new("RGB", (600, 800), color=(220, 220, 255))
        pdf_buf = io.BytesIO()
        page_1.save(pdf_buf, format="PDF", save_all=True, append_images=[page_2, page_3])
        multipage_pdf_bytes = pdf_buf.getvalue()

        # Also create a 1-page PDF for height comparison
        single_buf = io.BytesIO()
        page_1.save(single_buf, format="PDF")
        single_pdf_bytes = single_buf.getvalue()

        comp_single = compress_receipt_image(single_pdf_bytes, max_side=1200)
        comp_multi = compress_receipt_image(multipage_pdf_bytes, max_side=1200)
        self.assertIsNotNone(comp_single)
        self.assertIsNotNone(comp_multi)

        img_single = Image.open(io.BytesIO(comp_single))
        img_multi = Image.open(io.BytesIO(comp_multi))
        # Stitched 3-page image should have roughly 3x the height-to-width ratio of a 1-page PDF
        single_ratio = img_single.size[1] / img_single.size[0]
        multi_ratio = img_multi.size[1] / img_multi.size[0]
        self.assertGreater(multi_ratio, single_ratio * 2.7)

        # Verify Google Docs size calculation scales tall stitched PDFs up to 640 pt height
        w_pt, h_pt = tools._compute_proof_image_size_pt(comp_multi, max_w_pt=210.0, max_h_pt=300.0)
        self.assertGreater(h_pt, 500.0)
        self.assertLessEqual(h_pt, 640.0)
        self.assertGreater(w_pt, 150.0)

    def test_gdoc_table_populates_each_receipt_into_separate_row(self):
        def _cell(start, text):
            end = start + len(text) + 1
            return {
                "startIndex": start - 1,
                "endIndex": end,
                "content": [
                    {
                        "startIndex": start,
                        "endIndex": end,
                        "paragraph": {"elements": [{"textRun": {"content": text + "\n"}}]},
                    }
                ],
            }

        def _dropdown_cell(start, display_value="Choose"):
            end = start + 2
            return {
                "startIndex": start - 1,
                "endIndex": end,
                "content": [
                    {
                        "startIndex": start,
                        "endIndex": end,
                        "paragraph": {
                            "elements": [
                                {
                                    "startIndex": start,
                                    "endIndex": start + 1,
                                    "dropdown": {"dropdownProperties": {"displayValue": display_value}},
                                },
                                {
                                    "startIndex": start + 1,
                                    "endIndex": end,
                                    "textRun": {"content": "\n"},
                                },
                            ]
                        },
                    }
                ],
            }

        initial_doc = {
            "body": {
                "content": [
                    {
                        "startIndex": 50,
                        "table": {
                            "tableRows": [
                                {
                                    "tableCells": [
                                        _cell(55, "Item #"),
                                        _cell(65, "Category"),
                                        _cell(80, "Description of Expense"),
                                        _cell(110, "Original Cost"),
                                        _cell(130, "Cost in Approved Currency"),
                                    ]
                                },
                                {
                                    "tableCells": [
                                        _cell(160, "1"),
                                        _dropdown_cell(165, "Choose"),
                                        _cell(175, "{{Desc}}"),
                                        _cell(190, "{{SUM PL}}"),
                                        _cell(205, "{{SUM USD}}"),
                                    ]
                                },
                                {
                                    "tableCells": [
                                        _cell(220, ""),
                                        _cell(225, ""),
                                        _cell(230, "Total Spent (Sum from above)"),
                                        _cell(265, "{{TOTAL SUM PL}}"),
                                        _cell(285, "{{TOTAL SUM USD}}"),
                                    ]
                                },
                                {
                                    "tableCells": [
                                        _cell(310, ""),
                                        _cell(315, ""),
                                        _cell(320, "My Approved Budget Limit"),
                                        _cell(350, ""),
                                        _cell(355, ""),
                                    ]
                                },
                            ]
                        },
                    }
                ]
            }
        }
        updated_doc = {
            "body": {
                "content": [
                    {
                        "startIndex": 50,
                        "table": {
                            "tableRows": [
                                {
                                    "tableCells": [
                                        _cell(55, "Item #"),
                                        _cell(65, "Category"),
                                        _cell(80, "Description of Expense"),
                                        _cell(110, "Original Cost"),
                                        _cell(130, "Cost in Approved Currency"),
                                    ]
                                },
                                {
                                    "tableCells": [
                                        _cell(160, "1"),
                                        _dropdown_cell(165, "Choose"),
                                        _cell(170, "{{Desc}}"),
                                        _cell(175, "{{SUM PL}}"),
                                        _cell(180, "{{SUM USD}}"),
                                    ]
                                },
                                {
                                    "tableCells": [
                                        _cell(190, ""),
                                        _cell(195, ""),
                                        _cell(200, ""),
                                        _cell(205, ""),
                                        _cell(210, ""),
                                    ]
                                },
                                {
                                    "tableCells": [
                                        _cell(220, ""),
                                        _cell(225, ""),
                                        _cell(230, "Total Spent (Sum from above)"),
                                        _cell(265, "{{TOTAL SUM PL}}"),
                                        _cell(285, "{{TOTAL SUM USD}}"),
                                    ]
                                },
                                {
                                    "tableCells": [
                                        _cell(310, ""),
                                        _cell(315, ""),
                                        _cell(320, "My Approved Budget Limit"),
                                        _cell(350, ""),
                                        _cell(355, ""),
                                    ]
                                },
                            ]
                        },
                    }
                ]
            }
        }

        warnings = tools._diagnose_gdoc_template(initial_doc)
        self.assertTrue(any("SUM PL" in w for w in warnings))
        self.assertTrue(any("Choose" in w for w in warnings))

        docs_service = mock.MagicMock()
        docs_service.documents().get().execute.return_value = updated_doc
        receipts_data = [
            {"category": "Venue", "desc": "Adwall Production", "sum_curr": "1360.00 PLN", "sum_target": "359.06 USD"},
            {
                "category": "Transport",
                "desc": "Train Warsaw-Krakow",
                "sum_curr": "169.00 PLN",
                "sum_target": "44.62 USD",
            },
        ]
        ok = tools._populate_gdoc_expenses_table(
            docs_service=docs_service,
            google_doc_id="doc-123",
            initial_doc=initial_doc,
            receipts_data=receipts_data,
            total_curr_str="1529.00 PLN",
            total_target_str="403.68 USD",
            approved_budget="500.00 USD",
        )
        self.assertTrue(ok)
        self.assertEqual(docs_service.documents().batchUpdate.call_count, 2)
        first_reqs = docs_service.documents().batchUpdate.call_args_list[0].kwargs["body"]["requests"]
        # Only 1 extra row inserted; original Row 1 (with dropdown chip) is never deleted!
        self.assertEqual(len(first_reqs), 1)
        self.assertIn("insertTableRow", first_reqs[0])
        second_reqs = docs_service.documents().batchUpdate.call_args_list[1].kwargs["body"]["requests"]
        inserted_texts = [r["insertText"]["text"] for r in second_reqs if "insertText" in r]
        # Dropdown cell in Row 1 is preserved (not overwritten with "Venue")
        self.assertNotIn("Venue", inserted_texts)
        self.assertIn("Adwall Production", inserted_texts)
        self.assertIn("Train Warsaw-Krakow", inserted_texts)
        self.assertIn("1529.00 PLN", inserted_texts)
        self.assertIn("403.68 USD", inserted_texts)
        self.assertIn("500.00 USD", inserted_texts)


class NoFallbackExchangeRateTests(unittest.TestCase):
    def test_no_fallback_when_public_rates_unavailable(self):
        with mock.patch("agents.receipt_scanner.tools.requests.get", side_effect=OSError("network down")):
            pub = tools.fetch_public_rate_to_pln("GBP")
            self.assertFalse(pub["success"])
            self.assertIn("enter the exchange rate manually", pub["error"])
            with self.assertRaises(RuntimeError):
                tools.get_nbp_rate("GBP")
            ex = tools.get_exchange_rate("GBP", "PLN")
            self.assertFalse(ex["success"])
            self.assertIn("enter the exchange rate manually", ex["error"])

    def test_export_returns_error_when_rate_unavailable(self):
        with mock.patch.object(tools, "get_usd_pln_rate", return_value={"success": False, "error": "rate offline"}):
            res = tools.export_summary_to_google_doc(
                title="Expense_report_17_05_2026",
                receipts_data=[
                    {
                        "category": "Transport",
                        "desc": "Uber Ride",
                        "original_amount": 100.0,
                        "currency": "PLN",
                    }
                ],
                target_currency="USD",
            )
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "EXCHANGE_RATE_UNAVAILABLE")
        self.assertIn("manually in a text message", res["message"])

    def test_user_supplied_custom_rates_work_without_live_api(self):
        with mock.patch.object(tools, "get_nbp_rate", side_effect=RuntimeError("offline")):
            result = tools.show_receipt_summary(
                [KAUFLAND, UBER],
                target_currency="USD",
                exchange_rate=4.0,
                custom_rates={"EUR": 4.3},
            )
        self.assertTrue(result["success"])
        self.assertNotIn("rate_error", result)
        self.assertEqual(result["grand_total"], 52.62)

    def test_group_and_sort_receipts_and_reorder_proofs(self):
        scattered_receipts = [
            {"category": "Venue", "desc": "DevFest Printing Services", "original_amount": 100.0, "currency": "PLN"},
            {"category": "Transport", "desc": "Train Warsaw-Krakow", "original_amount": 169.0, "currency": "PLN"},
            {"category": "Venue", "desc": "Cardboard Shape Cutting", "original_amount": 80.0, "currency": "PLN"},
            {"category": "Transport", "desc": "Train Krakow-Warsaw", "original_amount": 169.0, "currency": "PLN"},
            {"category": "Venue", "desc": "DevFest Printing Services", "original_amount": 250.0, "currency": "PLN"},
        ]
        session_images = [
            b"proof_0_print1",
            b"proof_1_train1",
            b"proof_2_cardboard",
            b"proof_3_train2",
            b"proof_4_print2",
        ]

        grouped = group_and_sort_receipts(scattered_receipts)
        grouped_descs = [r["desc"] for r in grouped]
        # Transport items (Train) come together, and Venue printing items come together
        self.assertEqual(
            grouped_descs,
            [
                "Train Krakow-Warsaw",
                "Train Warsaw-Krakow",
                "Cardboard Shape Cutting",
                "DevFest Printing Services",
                "DevFest Printing Services",
            ],
        )

        reordered_proofs = docx_generator.reorder_proofs_for_grouped_receipts(grouped, session_images)
        self.assertEqual(
            reordered_proofs,
            [
                b"proof_3_train2",
                b"proof_1_train1",
                b"proof_2_cardboard",
                b"proof_0_print1",
                b"proof_4_print2",
            ],
        )

    def test_show_receipt_summary_returns_grouped_order(self):
        scattered = [
            {
                "merchant": "Drukarnia",
                "desc": "DevFest Printing Services",
                "category": "Venue",
                "currency": "PLN",
                "total": 100.0,
            },
            {
                "merchant": "PKP",
                "desc": "Train Warsaw-Krakow",
                "category": "Transport",
                "currency": "PLN",
                "total": 169.0,
            },
            {
                "merchant": "Kaufland",
                "desc": "Bottled Water Cisowianka",
                "category": "Food & drinks",
                "currency": "PLN",
                "total": 45.0,
            },
            {
                "merchant": "Adwall",
                "desc": "Adwall Production",
                "category": "Venue",
                "currency": "PLN",
                "total": 1360.0,
            },
        ]
        res = tools.show_receipt_summary(scattered, target_currency="PLN")
        self.assertTrue(res["success"])
        card_descs = [r["description"] for r in res["ui"]["receipts"]]
        self.assertEqual(
            card_descs,
            [
                "Bottled Water Cisowianka",
                "Train Warsaw-Krakow",
                "Adwall Production",
                "DevFest Printing Services",
            ],
        )

    def test_reorder_proofs_respects_explicit_attachment_index(self):
        receipts = [
            {"category": "Venue", "desc": "MicroSD Memory Card", "attachment_index": 3},
            {"category": "Venue", "desc": "LED Lighting Lamp", "attachment_index": 1},
            {"category": "Venue", "desc": "Samsung External SSD", "attachment_index": 4},
            {"category": "Venue", "desc": "RGB Tube Light", "attachment_index": 2},
        ]
        session_images = [
            b"attachment_1_led_lamp",
            b"attachment_2_rgb_tube",
            b"attachment_3_microsd_card",
            b"attachment_4_samsung_ssd",
        ]
        grouped = group_and_sort_receipts(receipts)
        reordered = docx_generator.reorder_proofs_for_grouped_receipts(grouped, session_images)
        self.assertEqual(
            [r["desc"] for r in grouped],
            [
                "MicroSD Memory Card",
                "Samsung External SSD",
                "LED Lighting Lamp",
                "RGB Tube Light",
            ],
        )
        self.assertEqual(
            reordered,
            [
                b"attachment_3_microsd_card",
                b"attachment_4_samsung_ssd",
                b"attachment_1_led_lamp",
                b"attachment_2_rgb_tube",
            ],
        )


if __name__ == "__main__":
    unittest.main()
