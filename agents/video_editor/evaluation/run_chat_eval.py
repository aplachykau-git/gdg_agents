"""Run video-editor ADK chat evaluations for both confirmation configurations."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path

EVALUATION_DIRECTORY = Path(__file__).resolve().parent
EVAL_SET = EVALUATION_DIRECTORY / "video_editor_chat_eval_set.json"
EVAL_CONFIG = EVALUATION_DIRECTORY / "video_editor_chat_eval_config.json"


def run(adk_command: str) -> int:
    for value in ("false", "true"):
        environment = os.environ | {"VIDEO_EDITOR_REQUIRE_CONFIRMATION": value}
        command = [
            *shlex.split(adk_command),
            "eval",
            str(EVALUATION_DIRECTORY),
            str(EVAL_SET),
            "--config_file_path",
            str(EVAL_CONFIG),
            "--print_detailed_results",
        ]
        process = subprocess.run(command, env=environment, check=False)
        if process.returncode:
            return process.returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adk", required=True)
    return run(parser.parse_args().adk)


if __name__ == "__main__":
    raise SystemExit(main())
