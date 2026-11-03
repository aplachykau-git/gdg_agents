"""Receipt recognition summary: deterministic totals, conversion, budget and copy text."""

import unittest
from unittest import mock

from agents.receipt_scanner import tools
from agents.receipt_scanner.summary import _num, build_receipt_summary, parse_budget

RATES = {"PLN": 1.0, "USD": 4.0, "EUR": 4.3}


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


class ShowReceiptSummaryToolTests(unittest.TestCase):
    def test_returns_ui_payload(self):
        with mock.patch.object(tools, "get_nbp_rate", side_effect=rate):
            result = tools.show_receipt_summary([KAUFLAND, UBER], "USD", "")
        self.assertTrue(result["success"])
        self.assertEqual(result["ui"]["type"], "receipt_summary")
        self.assertEqual(result["grand_total"], 52.62)
        self.assertIn("text", result["ui"])

    def test_agent_exposes_tool(self):
        from agents.receipt_scanner.agent import receipt_agent

        names = [getattr(t, "__name__", "") for t in receipt_agent.tools]
        self.assertIn("show_receipt_summary", names)
        self.assertLess(names.index("show_receipt_summary"), names.index("export_summary_to_google_doc"))


if __name__ == "__main__":
    unittest.main()
