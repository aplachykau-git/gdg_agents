"""Run the held-out few-shot judge set and report compact agreement statistics."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from typing import Any

from google import genai
from google.genai import errors as genai_errors

from agents.gemini_config import get_gemini_client
from agents.linkedin_post_generator.evaluation.evaluator import (
    build_few_shot_judge_prompt,
    load_judge_examples,
    validate_judge_result,
)


def _parse_json_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(stripped)


def judge_example(client: genai.Client, model: str, example: dict[str, Any]) -> dict[str, Any]:
    prompt = build_few_shot_judge_prompt(
        example["criterion"],
        example["source"],
        example["post_body"],
    )
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"temperature": 0, "response_mime_type": "application/json"},
            )
            break
        except genai_errors.ClientError as error:
            if error.code != 429 or attempt == 2:
                raise
            retry_match = re.search(r"retry in (\d+)", str(error), re.IGNORECASE)
            retry_seconds = int(retry_match.group(1)) if retry_match else 30
            time.sleep(retry_seconds + 1)
    return validate_judge_result(_parse_json_response(response.text or ""))


def run(model: str, score_tolerance: int) -> int:
    client = get_gemini_client()
    examples = load_judge_examples("eval")
    results = []
    for example in examples:
        actual = judge_example(client, model, example)
        verdict_match = actual["verdict"] == example["verdict"]
        if example["verdict"] == "unknown":
            score_match = actual["score"] is None
        else:
            score_match = (
                isinstance(actual["score"], int) and abs(actual["score"] - example["score"]) <= score_tolerance
            )
        results.append(
            {
                "criterion": example["criterion"],
                "expected": {"verdict": example["verdict"], "score": example["score"]},
                "actual": actual,
                "passed": verdict_match and score_match,
            }
        )

    passed = sum(result["passed"] for result in results)
    artifact = {
        "dataset": "linkedin_judge_held_out_eval_v1",
        "model": model,
        "passed": passed,
        "total": len(results),
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "results": results,
    }
    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    return 0 if passed == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.getenv("LINKEDIN_JUDGE_MODEL", "gemini-3.7-flash"))
    parser.add_argument("--score-tolerance", type=int, default=20)
    arguments = parser.parse_args()
    return run(arguments.model, arguments.score_tolerance)


if __name__ == "__main__":
    raise SystemExit(main())
