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
SUMMARY_TOOL_NAME = "show_receipt_summary"
RATE_TOOL_NAMES = {"get_exchange_rate", "get_usd_pln_rate"}
ALLOWED_CATEGORIES = {"Transport", "Hotel", "Food & drinks", "Swag", "Prizes", "Venue"}
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


def evaluate_batch_workflow_contract(
    tool_calls: list[Any],
    require_rate_first: bool = True,
) -> list[RuleResult]:
    """
    Evaluate multi-receipt workflow invariants:
    1. Exchange rate tool called before summary/export when conversion is needed.
    2. Both `show_receipt_summary` and `export_summary_to_google_doc` are called once.
    3. Every exported receipt uses an allowed category and valid attachment_index when present.
    4. Summary and export calls contain the same number of receipts in matching grouped order.
    """
    names = [getattr(call, "name", "") for call in tool_calls]
    summary_calls = [call for call in tool_calls if getattr(call, "name", "") == SUMMARY_TOOL_NAME]
    export_calls = [call for call in tool_calls if getattr(call, "name", "") == EXPORT_TOOL_NAME]

    rules: list[RuleResult] = []
    if require_rate_first:
        rate_positions = [i for i, n in enumerate(names) if n in RATE_TOOL_NAMES]
        later_positions = [i for i, n in enumerate(names) if n in {SUMMARY_TOOL_NAME, EXPORT_TOOL_NAME}]
        rate_first_ok = bool(rate_positions) and (not later_positions or min(rate_positions) < min(later_positions))
        rules.append(
            RuleResult(
                "rate_fetched_first",
                rate_first_ok,
                f"Expected exchange rate tool before summary/export; call sequence was {names!r}.",
            )
        )

    rules.append(
        RuleResult(
            "single_summary_and_export",
            len(summary_calls) == 1 and len(export_calls) == 1,
            f"Expected 1 summary and 1 export call; got {len(summary_calls)} summary and {len(export_calls)} export.",
        )
    )
    if len(summary_calls) != 1 or len(export_calls) != 1:
        return rules

    summary_args = getattr(summary_calls[0], "args", None) or {}
    export_args = getattr(export_calls[0], "args", None) or {}
    summary_receipts = summary_args.get("receipts") or []
    export_receipts = export_args.get("receipts_data") or []

    same_len = (
        isinstance(summary_receipts, list)
        and isinstance(export_receipts, list)
        and len(summary_receipts) == len(export_receipts)
        and len(export_receipts) > 0
    )
    rules.append(
        RuleResult(
            "matching_receipt_counts",
            same_len,
            f"Summary has {len(summary_receipts)} receipts while export has {len(export_receipts)}.",
        )
    )
    if not same_len:
        return rules

    valid_categories = all(isinstance(r, dict) and r.get("category") in ALLOWED_CATEGORIES for r in export_receipts)
    rules.append(
        RuleResult(
            "valid_categories",
            valid_categories,
            "All exported receipts must use one of the six canonical categories.",
        )
    )

    summary_descs = [str(r.get("desc", "")).strip() for r in summary_receipts if isinstance(r, dict)]
    export_descs = [str(r.get("desc", "")).strip() for r in export_receipts if isinstance(r, dict)]
    rules.append(
        RuleResult(
            "summary_export_sequence_match",
            summary_descs == export_descs,
            f"Summary order {summary_descs!r} did not match export order {export_descs!r}.",
        )
    )

    att_indices = [r.get("attachment_index") for r in export_receipts if isinstance(r, dict)]
    if any(idx is not None for idx in att_indices):
        valid_att = sorted(idx for idx in att_indices if isinstance(idx, int)) == list(
            range(1, len(export_receipts) + 1)
        )
        rules.append(
            RuleResult(
                "attachment_index_bijection",
                valid_att,
                f"Expected 1..{len(export_receipts)} attachment_index values; got {att_indices!r}.",
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
