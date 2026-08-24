"""Deterministic checks and few-shot semantic judging for LinkedIn posts."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from google.adk.evaluation.eval_case import Invocation
from google.adk.evaluation.eval_metrics import (
    EvalMetric,
    EvalStatus,
    Interval,
    MetricInfo,
    MetricValueInfo,
)
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult

Verdict = Literal["pass", "fail", "unknown"]

REQUIRED_FIELDS = (
    "speaker_name",
    "position",
    "company",
    "speaker_bio",
    "talk_title",
    "talk_description",
)
APPROVED_EMOJIS = ("🚀", "💻", "🧠", "⚡", "📱")
FORBIDDEN_HEADINGS = (
    "key takeaways",
    "what you will learn",
    "speaker bio",
    "session value",
)
VARIANT_PATTERN = re.compile(r"(?m)^### Variant ([1-9]\d*): ([^\n]+)\s*$")
HASHTAG_PATTERN = re.compile(r"(?<!\w)#\w+")


@dataclass(frozen=True)
class Variant:
    number: int
    name: str
    body: str


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    passed: bool
    explanation: str


def _package_file(name: str) -> Path:
    return Path(__file__).with_name(name)


def load_judge_examples(dataset: Literal["train", "eval"]) -> list[dict[str, Any]]:
    """Load only the requested judge dataset."""
    filename = "judge_train.json" if dataset == "train" else "judge_eval.json"
    with _package_file(filename).open(encoding="utf-8") as file:
        return json.load(file)["examples"]


def normalize_text(text: str) -> str:
    """Normalize text for title-leak and duplicate comparisons."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_text(content: Any) -> str:
    """Extract text from ADK Content, dictionaries, or plain strings."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts = content.get("parts") or []
    else:
        parts = getattr(content, "parts", None) or []

    chunks: list[str] = []
    for part in parts:
        text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
        if text:
            chunks.append(text)
    return "".join(chunks).strip()


def parse_user_fields(user_text: str) -> dict[str, str]:
    """Parse labeled inputs used by the repository's ADK eval fixtures."""
    aliases = {
        "speaker_name": ("speaker name", "speaker"),
        "position": ("position", "role"),
        "company": ("company",),
        "speaker_bio": ("speaker bio", "bio"),
        "talk_title": ("talk title", "title"),
        "talk_description": ("talk description", "description"),
        "registration_link": ("registration link", "registration url", "link"),
    }
    parsed: dict[str, str] = {}
    for key, labels in aliases.items():
        for label in labels:
            match = re.search(
                rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$",
                user_text,
            )
            if match:
                parsed[key] = match.group(1).strip()
                break
    return parsed


def parse_speakers(user_text: str) -> list[dict[str, str]]:
    """Parse the primary and ordinal-labelled speakers used in the eval set."""
    speaker_labels = (
        ("", "speaker_name"),
        ("second ", "speaker_name"),
        ("third ", "speaker_name"),
        ("fourth ", "speaker_name"),
    )
    field_labels = {
        "speaker_name": "speaker name",
        "position": "speaker position",
        "company": "speaker company",
        "speaker_bio": "speaker bio",
        "talk_title": "speaker talk title",
        "talk_description": "speaker talk description",
    }
    speakers: list[dict[str, str]] = []
    for prefix, _ in speaker_labels:
        current: dict[str, str] = {}
        for field, label in field_labels.items():
            if prefix:
                pattern_label = f"{prefix}{label}"
            elif field == "speaker_name":
                pattern_label = "speaker name"
            else:
                pattern_label = label.replace("speaker ", "")
            match = re.search(
                rf"(?im)^\s*{re.escape(pattern_label)}\s*:\s*(.+?)\s*$",
                user_text,
            )
            if match:
                current[field] = match.group(1).strip()
        if current.get("speaker_name"):
            speakers.append(current)
    return speakers


def parse_variants(response: str) -> list[Variant]:
    """Split a generated response into its explicitly headed variants."""
    matches = list(VARIANT_PATTERN.finditer(response))
    variants: list[Variant] = []
    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(response)
        variants.append(
            Variant(
                number=int(match.group(1)),
                name=match.group(2).strip(),
                body=response[match.end() : next_start].strip(),
            )
        )
    return variants


def missing_fields(fields: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not fields.get(field, "").strip()]


def _contains_name_tag(body: str, speaker_name: str) -> bool:
    names = [part for part in speaker_name.split() if part]
    return bool(names) and f"@{' '.join(names)}".casefold() in body.casefold()


def _paragraphs(body: str) -> list[str]:
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", body)
        if paragraph.strip() and paragraph.strip() not in {"---", "***"} and not _is_hashtag_or_link_block(paragraph)
    ]


def _is_hashtag_or_link_block(paragraph: str) -> bool:
    """Ignore non-prose footer blocks when evaluating CTA and paragraph count."""
    without_hashtags = HASHTAG_PATTERN.sub("", paragraph)
    without_links = re.sub(r"https?://\S+|\[[^\]]+\]\([^)]+\)|\[[^\]]+\]", "", without_hashtags)
    without_link_labels = re.sub(
        r"(?i)\b(register here|sign up(?: for the event)?|link to register|"
        r"registration link|save your spot here|learn more|details)\s*:?",
        "",
        without_links,
    )
    without_markers = re.sub(r"[\s🔗👉🎟️☝️]", "", without_link_labels)
    return not without_markers


def _has_cta(body: str) -> bool:
    cta_terms = (
        "register",
        "sign up",
        "signup",
        "secure your spot",
        "save your seat",
        "reserve your spot",
        "reserve your place",
        "reserve your seat",
        "grab your ticket",
        "join us",
        "stay tuned",
        "follow gdg",
        "don't miss",
        "dont miss",
        "join the conversation",
    )
    return any(term in body.casefold() for term in cta_terms)


def _has_forbidden_heading(body: str) -> bool:
    return any(re.search(rf"(?im)^\s*(?:#+\s*)?{re.escape(heading)}\s*:", body) for heading in FORBIDDEN_HEADINGS)


def _rule(rule_id: str, condition: bool, explanation: str) -> RuleResult:
    return RuleResult(rule_id, condition, explanation)


def _is_explicit_recap(request_text: str) -> bool:
    return "recap" in request_text.casefold()


def _speaker_for_variant_group(
    speakers: list[dict[str, str]], variant_index: int, is_recap: bool
) -> list[dict[str, str]]:
    if is_recap:
        return speakers
    return [speakers[variant_index // 3]]


def evaluate_response(
    response: str,
    fields: dict[str, str],
    *,
    speakers: list[dict[str, str]] | None = None,
    request_text: str = "",
) -> list[RuleResult]:
    """Apply deterministic generator contract checks to a complete-input response."""
    variants = parse_variants(response)
    speakers = speakers or [fields]
    is_recap = len(speakers) > 1 and _is_explicit_recap(request_text)
    expected_count = 3 if is_recap else 3 * len(speakers)
    expected_numbers = [1, 2, 3] if is_recap else [number for _ in speakers for number in (1, 2, 3)]
    expected_community_tag = f"#GDG{re.sub(r'\\s+', '', fields.get('community_name', 'Krakow'))}"
    rules: list[RuleResult] = [
        _rule(
            "variant_count_and_headers",
            len(variants) == expected_count
            and [variant.number for variant in variants] == expected_numbers
            and all(
                variant.name and not (variant.name.startswith("(") and variant.name.endswith(")"))
                for variant in variants
            ),
            "Expected exactly three `### Variant N: <Variant name>` headers per requested speaker, or three for a recap.",
        )
    ]
    if len(variants) != expected_count:
        return rules

    normalized_bodies = [normalize_text(variant.body) for variant in variants]
    variant_speakers = [_speaker_for_variant_group(speakers, index, is_recap) for index in range(len(variants))]
    rules.extend(
        [
            _rule(
                "talk_title_not_in_body",
                all(
                    all(normalize_text(speaker["talk_title"]) not in body for speaker in speaker_group)
                    for body, speaker_group in zip(normalized_bodies, variant_speakers, strict=True)
                ),
                "The normalized full talk title must not appear in any variant body.",
            ),
            _rule(
                "speaker_tag",
                all(
                    all(_contains_name_tag(variant.body, speaker["speaker_name"]) for speaker in speaker_group)
                    for variant, speaker_group in zip(variants, variant_speakers, strict=True)
                ),
                "Every variant must include each relevant supplied speaker as an @ tag.",
            ),
            _rule(
                "position_and_company",
                all(
                    all(
                        speaker["position"].casefold() in variant.body.casefold()
                        and speaker["company"].casefold() in variant.body.casefold()
                        for speaker in speaker_group
                    )
                    for variant, speaker_group in zip(variants, variant_speakers, strict=True)
                ),
                "Every variant must mention each relevant supplied position and company in prose.",
            ),
            _rule(
                "community_hashtag_exactly_once",
                all(variant.body.count(expected_community_tag) == 1 for variant in variants),
                f"Every variant must include exactly one `{expected_community_tag}` hashtag.",
            ),
            _rule(
                "hashtag_count",
                all(3 <= len(HASHTAG_PATTERN.findall(variant.body)) <= 4 for variant in variants),
                "Every variant must contain exactly 3–4 hashtags.",
            ),
            _rule(
                "cta",
                all(_has_cta(variant.body) for variant in variants),
                "Every variant must include an inviting registration-oriented CTA.",
            ),
            _rule(
                "narrative_format",
                all(
                    2 <= len(_paragraphs(variant.body)) <= 3
                    and any(emoji in variant.body for emoji in APPROVED_EMOJIS)
                    and not _has_forbidden_heading(variant.body)
                    for variant in variants
                ),
                "Every variant needs 2–3 prose paragraphs, an approved emoji, and no forbidden robotic heading.",
            ),
            _rule(
                "variant_differentiation",
                len(set(normalized_bodies)) == len(normalized_bodies),
                "Variants must not be exact normalized duplicates.",
            ),
        ]
    )
    return rules


def evaluate_missing_input_response(response: str, fields: dict[str, str]) -> list[RuleResult]:
    """Check that incomplete inputs produce only a targeted clarification."""
    missing = missing_fields(fields)
    response_lower = response.casefold()
    variants = parse_variants(response)
    mentions_all_missing = all(
        field.replace("_", " ") in response_lower or (field == "speaker_bio" and "bio" in response_lower)
        for field in missing
    )
    return [
        _rule(
            "missing_fields_clarification",
            bool(missing) and mentions_all_missing,
            "The response must request every missing required field.",
        ),
        _rule(
            "no_partial_generation",
            bool(missing) and not variants,
            "The response must not generate post variants while required inputs are missing.",
        ),
        _rule(
            "no_optional_field_request",
            "registration link" not in response_lower,
            "The response must not ask for the optional registration link.",
        ),
    ]


def _result_for_invocation(
    invocation: Invocation,
    rule_results: list[RuleResult],
) -> PerInvocationResult:
    passed = all(result.passed for result in rule_results)
    return PerInvocationResult(
        actual_invocation=invocation,
        score=100.0 if passed else 0.0,
        eval_status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
    )


def linkedin_contract_metric(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: list[Invocation] | None = None,
    conversation_scenario: Any = None,
) -> EvaluationResult:
    """ADK custom metric: deterministic contract checks for every user turn."""
    del eval_metric, expected_invocations, conversation_scenario
    per_invocation: list[PerInvocationResult] = []
    all_rule_results: list[RuleResult] = []
    accumulated_fields: dict[str, str] = {}
    accumulated_speakers: list[dict[str, str]] = []
    accumulated_request_text = ""

    for invocation in actual_invocations:
        user_text = extract_text(invocation.user_content)
        accumulated_request_text += f"\n{user_text}"
        user_fields = parse_user_fields(user_text)
        accumulated_fields.update(user_fields)
        parsed_speakers = parse_speakers(accumulated_request_text)
        if parsed_speakers:
            accumulated_speakers = parsed_speakers
        response = extract_text(invocation.final_response)
        if missing_fields(accumulated_fields):
            rules = evaluate_missing_input_response(response, accumulated_fields)
        else:
            accumulated_fields.setdefault("community_name", "Krakow")
            rules = evaluate_response(
                response,
                accumulated_fields,
                speakers=accumulated_speakers or [accumulated_fields],
                request_text=accumulated_request_text,
            )
        all_rule_results.extend(rules)
        per_invocation.append(_result_for_invocation(invocation, rules))

    passed = bool(per_invocation) and all(result.passed for result in all_rule_results)
    return EvaluationResult(
        overall_score=100.0 if passed else 0.0,
        overall_eval_status=EvalStatus.PASSED if passed else EvalStatus.FAILED,
        per_invocation_results=per_invocation,
    )


def linkedin_contract_metric_info() -> MetricInfo:
    """Describe the 0–100 aggregate metric exposed by the ADK config."""
    return MetricInfo(
        metric_name="linkedin_contract_score",
        description=("LinkedIn deterministic contract score: 100 when every release gate passes, otherwise 0."),
        metric_value_info=MetricValueInfo(interval=Interval(min_value=0.0, max_value=100.0)),
    )


JUDGE_SYSTEM_PROMPT = """You are a strict evaluator for LinkedIn speaker-post semantic quality.
Evaluate only the requested criterion. Do not assess copywriting style, hashtags, or formatting.

Return JSON only:
{"verdict":"pass|fail|unknown","score":<integer 0-100 or null>,"reason":"brief evidence-based explanation"}

Rules:
- Decide whether the source contains enough topic-specific evidence BEFORE judging the post.
- unknown: use this whenever the relevant source is generic, broad, reflective, empty, or otherwise lacks concrete topic-specific claims. If the source cannot establish a specific topic, you MUST return unknown even if the post introduces a clearly unrelated or unsupported topic. Do not infer an intended topic from the speaker bio, generic labels, narrative framing, or common professional knowledge.
- pass: use only when the source is sufficiently specific and supports the post body for the requested criterion.
- fail: use only when the source is sufficiently specific and the post body conflicts with, changes, or invents unsupported session content.
- unknown MUST use score null. pass/fail MUST use an integer from 0 to 100.

Topic alignment: first require a concrete talk title or description that identifies a topic, method, technology, problem, or outcome. If it does not, return unknown. Otherwise compare the post topic against talk title and talk description. A full title may be absent from the body; that is correct.
Bio/topic separation: first require a usable talk description that establishes session content. If it is absent or too vague, return unknown. Otherwise, credentials can come from the speaker bio, but session claims must come from the talk description. Bio-only technologies must not become session content.
"""


def build_few_shot_judge_prompt(
    criterion: str,
    source: dict[str, str],
    post_body: str,
) -> str:
    """Build the judge prompt from train data only; held-out examples stay excluded."""
    examples = [example for example in load_judge_examples("train") if example["criterion"] == criterion]
    serialized_examples = json.dumps(examples, ensure_ascii=False, indent=2)
    payload = json.dumps(
        {"criterion": criterion, "source": source, "post_body": post_body},
        ensure_ascii=False,
        indent=2,
    )
    return (
        f"{JUDGE_SYSTEM_PROMPT}\n\n"
        f"Few-shot training examples (use as decision patterns):\n{serialized_examples}\n\n"
        f"Evaluate this new item:\n{payload}"
    )


def validate_judge_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the required pass/fail/unknown structured judge output."""
    verdict = payload.get("verdict")
    score = payload.get("score")
    reason = payload.get("reason")
    if verdict not in {"pass", "fail", "unknown"}:
        raise ValueError("Judge verdict must be pass, fail, or unknown.")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Judge reason must be a non-empty string.")
    if verdict == "unknown":
        if score is not None:
            raise ValueError("Unknown judge verdict must have a null score.")
    elif not isinstance(score, int) or not 0 <= score <= 100:
        raise ValueError("Pass/fail judge verdicts require an integer score from 0 to 100.")
    return {"verdict": verdict, "score": score, "reason": reason.strip()}
