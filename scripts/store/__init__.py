"""Call store: persist provider API calls (inputs/outputs/errors/cost) + replay."""

import os

from scripts.store.calls import record, replay  # noqa: F401


def enable() -> None:
    """Install the recorder so provider calls are persisted (unless CALL_LOG=0)."""
    if os.getenv("CALL_LOG", "1") != "0":
        from scripts.providers import http  # lazy: avoids a store<->providers import cycle

        http.set_recorder(record)


def disable() -> None:
    """Stop recording calls."""
    from scripts.providers import http

    http.set_recorder(None)
