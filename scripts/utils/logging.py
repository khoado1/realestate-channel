"""Structured (JSON) logging for the content pipeline.

Separate from scripts.utils.console's Rich helpers: rprint/rpanel/rrule are
human-facing terminal output for an interactive run; this module is
machine-facing operational logging (retries, circuit-breaker transitions,
provider failures) — the signal a future log aggregator (Loki, per
docs/platform-architecture.md) needs once these scripts run as long-lived
workers instead of one-off CLI invocations. Logs go to stderr so they never
interleave with Rich's stdout output during an interactive run.
"""

import json
import logging
import os
import sys
import time


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a logger that emits one JSON object per line to stderr.

    Attach structured context with ``logger.info("msg", extra={"fields": {...}})``.
    Level is controlled by the ``LOG_LEVEL`` env var (default ``INFO``).
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        logger.propagate = False
    return logger
