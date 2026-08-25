"""Run deterministic receipt conversion evaluations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.receipt_scanner.tools import calculate_receipt_totals, normalise_receipts


def _case_file() -> Path:
    return Path(__file__).with_name("conversion_eval_cases.json")


def load_cases() -> dict[str, Any]:
    with _case_file().open(encoding="utf-8") as file:
        return json.load(file)


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    target_currency = case["target_currency"].upper().strip()
    rates = {currency.upper().strip(): float(rate) for currency, rate in case["rates_to_pln"].items()}

    def rate_to_pln(currency: str) -> float:
        return rates[currency.upper().strip()]

    actual_receipts = normalise_receipts(
        case["receipts"],
        target_currency,
        rates[target_currency],
        rate_to_pln,
    )
    source_total, target_total = calculate_receipt_totals(actual_receipts, target_currency)

    actual_values = [
        {
            "sum_curr": receipt["sum_curr"],
            "sum_target": receipt["sum_target"],
        }
        for receipt in actual_receipts
    ]
    failures = []
    if actual_values != case["expected_receipts"]:
        failures.append("receipt_values")
    if source_total != case["expected_source_total"]:
        failures.append("source_total")
    if target_total != case["expected_target_total"]:
        failures.append("target_total")

    return {
        "case_id": case["case_id"],
        "passed": not failures,
        "failures": failures,
        "expected": {
            "receipts": case["expected_receipts"],
            "source_total": case["expected_source_total"],
            "target_total": case["expected_target_total"],
        },
        "actual": {
            "receipts": actual_values,
            "source_total": source_total,
            "target_total": target_total,
        },
    }


def run() -> int:
    dataset = load_cases()
    results = [evaluate_case(case) for case in dataset["cases"]]
    passed = sum(result["passed"] for result in results)
    artifact = {
        "dataset": dataset["dataset_id"],
        "passed": passed,
        "total": len(results),
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "results": results,
    }
    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(run())
