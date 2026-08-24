"""Run ADK receipt extraction evaluations and enforce their exit status."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import time
from pathlib import Path

PASSED_STATUS = 1
EVALUATION_DIRECTORY = Path(__file__).resolve().parent
EVAL_SET = EVALUATION_DIRECTORY / "receipt_scanner_eval_set.json"
EVAL_CONFIG = EVALUATION_DIRECTORY / "receipt_scanner_eval_config.json"
EVAL_HISTORY = EVALUATION_DIRECTORY / ".adk" / "eval_history"


def _latest_result(started_at: float) -> Path | None:
    candidates = [path for path in EVAL_HISTORY.glob("*.evalset_result.json") if path.stat().st_mtime >= started_at]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def run(adk_command: str) -> int:
    started_at = time.time() - 1
    command = [
        *shlex.split(adk_command),
        "eval",
        str(EVALUATION_DIRECTORY),
        str(EVAL_SET),
        "--config_file_path",
        str(EVAL_CONFIG),
        "--print_detailed_results",
    ]
    process = subprocess.run(command, check=False)
    if process.returncode:
        return process.returncode

    result_path = _latest_result(started_at)
    if result_path is None:
        print("ADK did not write an extraction evaluation result.")
        return 1

    with result_path.open(encoding="utf-8") as file:
        result = json.load(file)
    with EVAL_SET.open(encoding="utf-8") as file:
        expected_ids = {case["eval_id"] for case in json.load(file)["eval_cases"]}
    actual_statuses = {case["eval_id"]: case.get("final_eval_status") for case in result.get("eval_case_results", [])}
    failures = sorted(eval_id for eval_id in expected_ids if actual_statuses.get(eval_id) != PASSED_STATUS)
    if failures:
        print(f"Receipt extraction evaluations failed: {', '.join(failures)}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adk", required=True)
    return run(parser.parse_args().adk)


if __name__ == "__main__":
    raise SystemExit(main())
