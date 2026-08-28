"""Deterministic ADK contract checks for video-editor chat evaluations."""

from __future__ import annotations

from typing import Any

from google.adk.evaluation.eval_case import Invocation, get_all_tool_calls
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult

TOOL_NAME = "create_video_card"


def _text(content: Any) -> str:
    parts = content.get("parts", []) if isinstance(content, dict) else getattr(content, "parts", []) or []
    return "".join(
        part.get("text", "") if isinstance(part, dict) else getattr(part, "text", "") or "" for part in parts
    )


def video_editor_chat_contract_metric(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None = None,
    conversation_scenario: Any = None,
) -> EvaluationResult:
    """Return 100 when every invocation satisfies its tool-call contract."""
    del eval_metric, expected_invocations, conversation_scenario
    results = []
    for invocation in actual_invocations:
        user_text = _text(invocation.user_content).casefold()
        calls = [call for call in get_all_tool_calls(invocation.intermediate_data) if call.name == TOOL_NAME]
        unrelated = "what can you do" in user_text or "capital of france" in user_text
        expected_no_call = unrelated
        passed = not calls if expected_no_call else bool(calls)
        results.append(
            PerInvocationResult(
                actual_invocation=invocation,
                score=100.0 if passed else 0.0,
                eval_status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
            )
        )
    passed = bool(results) and all(result.eval_status == EvalStatus.PASSED for result in results)
    return EvaluationResult(
        overall_score=100.0 if passed else 0.0,
        overall_eval_status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
        per_invocation_results=results,
    )
