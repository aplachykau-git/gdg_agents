"""Deterministic ADK contract checks for video-editor chat evaluations.

Each user turn is matched against EXPECTATIONS (first matching phrase wins) to decide which
tool calls are required / forbidden in that turn.
"""

from __future__ import annotations

from typing import Any

from google.adk.evaluation.eval_case import Invocation, get_all_tool_calls
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult

CARD_TOOLS = {"update_speaker", "propose_scenarios", "show_scenarios", "render_video", "get_card_status"}

# phrase in the user turn -> (tools that must be called, tools that must NOT be called)
EXPECTATIONS: list[tuple[str, set[str], set[str]]] = [
    ("capital of france", set(), CARD_TOOLS),
    ("what can you do", set(), CARD_TOOLS),
    ("render option 2", {"render_video"}, {"update_speaker"}),
    ("render option 1", {"render_video"}, set()),
    ("same speaker, but", {"propose_scenarios"}, set()),
    ("show me the options again", {"show_scenarios"}, {"propose_scenarios", "render_video"}),
    ("reliabel", set(), {"render_video"}),
]
DEFAULT_REQUIRED = {"update_speaker"}


def _text(content: Any) -> str:
    parts = content.get("parts", []) if isinstance(content, dict) else getattr(content, "parts", []) or []
    return "".join(
        part.get("text", "") if isinstance(part, dict) else getattr(part, "text", "") or "" for part in parts
    )


def expectation_for(user_text: str) -> tuple[set[str], set[str]]:
    lowered = user_text.casefold()
    for phrase, required, forbidden in EXPECTATIONS:
        if phrase in lowered:
            return required, forbidden
    return DEFAULT_REQUIRED, set()


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
        required, forbidden = expectation_for(_text(invocation.user_content))
        called = {call.name for call in get_all_tool_calls(invocation.intermediate_data)}
        passed = required <= called and not (forbidden & called)
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
