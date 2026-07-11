"""Shared event-publishing helper, and the gateway's event-sink wiring.

A different concern from structured logging (scripts/utils/logging.py,
machine-readable ops logs) and the call recorder (scripts/providers/http.py,
persisted call/cost records): this is for domain events — circuit breaker
transitions, completed provider calls, backlog writes — that a downstream
subscriber (console today, Kafka once EVENTS_PROVIDER=kafka is set) might
react to.

Publish failures are logged and swallowed here, same rule as the call
recorder: a broken event subscriber must never break the primary call flow.
"""

import os

from scripts.providers.registry import get_provider
from scripts.utils.logging import get_logger

log = get_logger(__name__)


def publish_event(event: str, payload: dict) -> None:
    """Publish ``event`` with ``payload`` via the configured ``events`` provider."""
    try:
        get_provider("events").publish(event, payload)
    except Exception as e:
        log.warning("event publish failed", extra={"fields": {"event": event, "error": str(e)}})


def wire_gateway_events() -> None:
    """Install ``publish_event`` as the gateway's circuit-breaker event sink.

    Lazy import keeps scripts.gateway free of any dependency on
    scripts.providers (same rule as the call-recorder wiring in
    scripts/store/__init__.py) — the gateway only ever calls back into
    whatever sink is installed here.
    """
    if os.getenv("EVENTS_LOG", "1") != "0":
        from scripts.gateway import circuit_breaker

        circuit_breaker.set_event_sink(publish_event)
