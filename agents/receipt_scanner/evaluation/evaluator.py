"""Deterministic critical-field evaluation for receipt extraction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.adk.evaluation.eval_case import Invocation, get_all_tool_calls
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult

EXPORT_TOOL_NAME = "export_summary_to_google_doc"
AMOUNT_TOLERANCE = 0.01
ISO_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    passed: bool
    explanation: str


def _fixture_manifest() -> dict[str, Any]:
    path = Path(__file__).with_name("receipt_fixtures.json")
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def load_fixtures() -> dict[str, dict[str, Any]]:
    return {fixture["file_name"]: fixture for fixture in _fixture_manifest()["fixtures"]}


def extract_text(content: Any) -> str:
    if content is None:
        return ""
    parts = content.get("parts", []) if isinstance(content, dict) else getattr(content, "parts", []) or []
    return "".join(
        part.get("text", "") if isinstance(part, dict) else getattr(part, "text", "") or "" for part in parts
    )


def fixture_for_user_text(user_text: str) -> dict[str, Any] | None:
    for file_name, fixture in load_fixtures().items():
        if file_name in user_text:
            return fixture
    return None


def evaluate_export_arguments(
    export_calls: list[Any],
    fixture: dict[str, Any] | None,
) -> list[RuleResult]:
    if fixture is None:
        return [RuleResult("known_fixture", False, "The prompt does not reference a locked fixture.")]

    rules = [
        RuleResult(
            "single_export",
            len(export_calls) == 1,
            f"Expected exactly one export call; received {len(export_calls)}.",
        )
    ]
    if len(export_calls) != 1:
        return rules

    arguments = getattr(export_calls[0], "args", None) or {}
    receipts = arguments.get("receipts_data")
    rules.append(
        RuleResult(
            "single_receipt",
            isinstance(receipts, list) and len(receipts) == 1,
            "The export must contain exactly one receipt.",
        )
    )
    if not isinstance(receipts, list) or len(receipts) != 1:
        return rules

    receipt = receipts[0]
    rules.append(
        RuleResult(
            "receipt_shape",
            isinstance(receipt, dict),
            "The exported receipt must be an object.",
        )
    )
    if not isinstance(receipt, dict):
        return rules

    expected = fixture["expected"]

    try:
        amount = float(receipt.get("original_amount"))
        expected_amount = float(expected["total"])
        amount_matches = abs(amount - expected_amount) <= AMOUNT_TOLERANCE
    except (TypeError, ValueError):
        amount = receipt.get("original_amount")
        amount_matches = False
    rules.append(
        RuleResult(
            "total",
            amount_matches,
            f"Expected total {expected['total']}; received {amount!r}.",
        )
    )

    currency = str(receipt.get("currency", "")).upper().strip()
    rules.append(
        RuleResult(
            "currency",
            currency == expected["currency"],
            f"Expected currency {expected['currency']}; received {currency or '<missing>'}.",
        )
    )
    rules.append(
        RuleResult(
            "date",
            receipt.get("date") == expected["date"],
            f"Expected date {expected['date']}; received {receipt.get('date')!r}.",
        )
    )

    image_path = str(receipt.get("image_path", ""))
    rules.append(
        RuleResult(
            "image_path",
            fixture["file_name"] in image_path,
            f"Expected image path to reference {fixture['file_name']}; received {image_path!r}.",
        )
    )

    target_currency = str(arguments.get("target_currency", "")).upper().strip()
    rules.append(
        RuleResult(
            "target_currency_shape",
            bool(ISO_CURRENCY_PATTERN.fullmatch(target_currency)),
            f"Expected a three-letter target currency; received {target_currency or '<missing>'}.",
        )
    )
    return rules


def critical_extraction_metric(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None = None,
    conversation_scenario: Any = None,
) -> EvaluationResult:
    """Return 100 only when every critical extraction rule passes."""
    del eval_metric, expected_invocations, conversation_scenario
    per_invocation = []
    all_rules = []

    for invocation in actual_invocations:
        fixture = fixture_for_user_text(extract_text(invocation.user_content))
        export_calls = [
            call for call in get_all_tool_calls(invocation.intermediate_data) if call.name == EXPORT_TOOL_NAME
        ]
        rules = evaluate_export_arguments(export_calls, fixture)
        all_rules.extend(rules)
        passed = all(rule.passed for rule in rules)
        per_invocation.append(
            PerInvocationResult(
                actual_invocation=invocation,
                score=100.0 if passed else 0.0,
                eval_status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
            )
        )

    passed = bool(per_invocation) and all(rule.passed for rule in all_rules)
    return EvaluationResult(
        overall_score=100.0 if passed else 0.0,
        overall_eval_status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
        per_invocation_results=per_invocation,
    )
