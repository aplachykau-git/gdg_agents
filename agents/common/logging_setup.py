"""Logging configuration for all agents.

* Locally: short human-readable lines.
* On Cloud Run (``K_SERVICE`` is set) or with ``LOG_FORMAT=json``: one JSON object per line with
  a ``severity`` field, which Cloud Logging turns into proper log levels and searchable fields.

``LOG_LEVEL`` (default INFO) controls verbosity. Safe to call more than once.
"""

from __future__ import annotations

import json
import logging
import os
import sys

_CONFIGURED = False
_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class CloudJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value if isinstance(value, (str, int, float, bool, type(None))) else repr(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    use_json = os.getenv("LOG_FORMAT", "").lower() == "json" or bool(os.getenv("K_SERVICE"))
    handler = logging.StreamHandler(sys.stdout)
    if use_json:
        handler.setFormatter(CloudJsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level_name)
    for noisy in ("httpx", "httpcore", "urllib3", "google_genai.models", "asyncio"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))
    _CONFIGURED = True
