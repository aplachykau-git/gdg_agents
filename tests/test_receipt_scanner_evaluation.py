import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from google.genai import types

from agents.receipt_scanner.evaluation import evaluator
from agents.receipt_scanner.evaluation.prepare_fixtures import _verify_image
from agents.receipt_scanner.evaluation.run_conversion_eval import evaluate_case
from agents.receipt_scanner.evaluation.run_extraction_eval import run as run_extraction_eval
from agents.receipt_scanner.tools import calculate_receipt_totals, normalise_receipts


class ReceiptExtractionEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {
            "file_name": "receipt.jpg",
            "expected": {
                "total": "11.50",
                "currency": "EUR",
                "date": "2013-11-05",
            },
        }

    def export_call(self, **overrides):
        receipt = {
            "original_amount": 11.5,
            "currency": "EUR",
            "date": "2013-11-05",
            "image_path": "/tmp/receipt.jpg",
        }
        receipt.update(overrides.pop("receipt", {}))
        arguments = {
            "receipts_data": [receipt],
            "target_currency": "USD",
        }
        arguments.update(overrides)
        return types.FunctionCall(
            name="export_summary_to_google_doc",
            args=arguments,
        )

    def assert_rule(self, rules, rule_id, expected):
        rule = next(rule for rule in rules if rule.rule_id == rule_id)
        self.assertEqual(rule.passed, expected)

    def test_valid_export_passes_all_rules(self):
        rules = evaluator.evaluate_export_arguments([self.export_call()], self.fixture)
        self.assertTrue(all(rule.passed for rule in rules))

    def test_numeric_string_amount_is_accepted(self):
        rules = evaluator.evaluate_export_arguments(
            [self.export_call(receipt={"original_amount": "11.50"})],
            self.fixture,
        )
        self.assert_rule(rules, "total", True)

    def test_wrong_total_fails(self):
        rules = evaluator.evaluate_export_arguments(
            [self.export_call(receipt={"original_amount": 12.0})],
            self.fixture,
        )
        self.assert_rule(rules, "total", False)

    def test_wrong_currency_fails(self):
        rules = evaluator.evaluate_export_arguments(
            [self.export_call(receipt={"currency": "USD"})],
            self.fixture,
        )
        self.assert_rule(rules, "currency", False)

    def test_wrong_date_fails(self):
        rules = evaluator.evaluate_export_arguments(
            [self.export_call(receipt={"date": "05.11.2013"})],
            self.fixture,
        )
        self.assert_rule(rules, "date", False)

    def test_no_export_fails(self):
        rules = evaluator.evaluate_export_arguments([], self.fixture)
        self.assert_rule(rules, "single_export", False)

    def test_duplicate_export_fails(self):
        call = self.export_call()
        rules = evaluator.evaluate_export_arguments([call, call], self.fixture)
        self.assert_rule(rules, "single_export", False)

    def test_empty_receipts_fail(self):
        rules = evaluator.evaluate_export_arguments(
            [self.export_call(receipts_data=[])],
            self.fixture,
        )
        self.assert_rule(rules, "single_receipt", False)

    def test_non_object_receipt_fails_without_exception(self):
        rules = evaluator.evaluate_export_arguments(
            [self.export_call(receipts_data=["invalid"])],
            self.fixture,
        )
        self.assert_rule(rules, "receipt_shape", False)

    def test_unknown_fixture_fails(self):
        rules = evaluator.evaluate_export_arguments([self.export_call()], None)
        self.assert_rule(rules, "known_fixture", False)


class ReceiptConversionTests(unittest.TestCase):
    def test_normalises_and_totals_mixed_currencies(self):
        rates = {"PLN": 1.0, "EUR": 4.5, "USD": 4.0}
        receipts = normalise_receipts(
            [
                {"original_amount": 40, "currency": "PLN"},
                {"original_amount": 20, "currency": "EUR"},
            ],
            "USD",
            rates["USD"],
            rates.__getitem__,
        )
        self.assertEqual(receipts[0]["sum_target"], "10.00 USD")
        self.assertEqual(receipts[1]["sum_target"], "22.50 USD")
        self.assertEqual(
            calculate_receipt_totals(receipts, "USD"),
            ("40.00 PLN, 20.00 EUR", "32.50 USD"),
        )

    def test_same_currency_does_not_resolve_rate(self):
        resolver = Mock(side_effect=AssertionError("Rate resolver must not be called."))
        receipts = normalise_receipts(
            [{"original_amount": 19.99, "currency": "EUR"}],
            "EUR",
            4.3,
            resolver,
        )
        self.assertEqual(receipts[0]["sum_target"], "19.99 EUR")
        resolver.assert_not_called()

    def test_conversion_case_detects_incorrect_expected_value(self):
        case = {
            "case_id": "incorrect",
            "target_currency": "USD",
            "rates_to_pln": {"PLN": 1.0, "USD": 4.0},
            "receipts": [{"original_amount": 120, "currency": "PLN"}],
            "expected_receipts": [{"sum_curr": "120.00 PLN", "sum_target": "40.00 USD"}],
            "expected_source_total": "120.00 PLN",
            "expected_target_total": "40.00 USD",
        }
        result = evaluate_case(case)
        self.assertFalse(result["passed"])
        self.assertIn("receipt_values", result["failures"])
        self.assertIn("target_total", result["failures"])

    def test_all_locked_conversion_cases_pass(self):
        case_path = (
            Path(__file__).parents[1] / "agents" / "receipt_scanner" / "evaluation" / "conversion_eval_cases.json"
        )
        with case_path.open(encoding="utf-8") as file:
            cases = json.load(file)["cases"]
        self.assertTrue(all(evaluate_case(case)["passed"] for case in cases))


class ReceiptFixtureVerificationTests(unittest.TestCase):
    def test_checksum_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.jpg"
            path.write_bytes(b"not an image")
            with self.assertRaises(ValueError):
                _verify_image(path, "0" * 64)

    @patch("agents.receipt_scanner.evaluation.prepare_fixtures.Image.open")
    def test_matching_checksum_verifies_image(self, image_open):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.jpg"
            path.write_bytes(b"fixture")
            digest = hashlib.sha256(b"fixture").hexdigest()
            context = image_open.return_value.__enter__.return_value
            _verify_image(path, digest)
            context.verify.assert_called_once_with()


class ReceiptExtractionRunnerTests(unittest.TestCase):
    @patch("agents.receipt_scanner.evaluation.run_extraction_eval._latest_result")
    @patch("agents.receipt_scanner.evaluation.run_extraction_eval.subprocess.run")
    def test_failing_adk_result_returns_non_zero(self, subprocess_run, latest_result):
        subprocess_run.return_value.returncode = 0
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "result.json"
            result.write_text(
                json.dumps({"eval_case_results": [{"eval_id": "failed_case", "final_eval_status": 2}]}),
                encoding="utf-8",
            )
            latest_result.return_value = result
            self.assertEqual(run_extraction_eval("adk"), 1)

    @patch("agents.receipt_scanner.evaluation.run_extraction_eval._latest_result")
    @patch("agents.receipt_scanner.evaluation.run_extraction_eval.subprocess.run")
    def test_passing_adk_result_returns_zero(self, subprocess_run, latest_result):
        subprocess_run.return_value.returncode = 0
        eval_set_path = (
            Path(__file__).parents[1] / "agents" / "receipt_scanner" / "evaluation" / "receipt_scanner_eval_set.json"
        )
        with eval_set_path.open(encoding="utf-8") as file:
            eval_ids = [case["eval_id"] for case in json.load(file)["eval_cases"]]
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "result.json"
            result.write_text(
                json.dumps(
                    {"eval_case_results": [{"eval_id": eval_id, "final_eval_status": 1} for eval_id in eval_ids]}
                ),
                encoding="utf-8",
            )
            latest_result.return_value = result
            self.assertEqual(run_extraction_eval("adk"), 0)


if __name__ == "__main__":
    unittest.main()
