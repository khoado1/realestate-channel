"""Kafka event publisher — an alternate ``events`` provider.

Selected via ``EVENTS_PROVIDER=kafka``. Tunables live in
scripts/config/providers.toml's ``[kafka]`` section (bootstrap servers, topic,
timeouts) per the config-not-code rule.

``api_version`` is set explicitly (rather than left to auto-detect) so
constructing the producer never blocks on an extra broker round-trip just to
negotiate the wire protocol version. ``max_block_ms``/``request_timeout_ms``
bound how long a publish can stall when the broker is unreachable — without
them, a send() to a dead/misconfigured broker can hang far longer than a
domain-event publish should ever be allowed to.
"""

from scripts.providers.base import EventPublisher, ProviderError
from scripts.providers.registry import register
from scripts.utils.config import load


@register("events", "kafka")
class KafkaPublisher(EventPublisher):
    def __init__(self):
        cfg = load("providers")["kafka"]
        self._topic = cfg["topic"]
        try:
            from kafka import KafkaProducer
        except ImportError as e:
            raise ProviderError(
                "kafka-python is not installed — add it to requirements.txt (see [kafka] "
                "in scripts/config/providers.toml)"
            ) from e

        import json

        try:
            self._producer = KafkaProducer(
                bootstrap_servers=cfg["bootstrap_servers"],
                api_version=tuple(cfg["api_version"]),
                bootstrap_timeout_ms=cfg["bootstrap_timeout_ms"],
                request_timeout_ms=cfg["request_timeout_ms"],
                max_block_ms=cfg["max_block_ms"],
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
        except Exception as e:
            raise ProviderError(f"Kafka producer setup failed: {e}") from e

    def publish(self, event: str, payload: dict) -> None:
        try:
            future = self._producer.send(self._topic, {"event": event, "payload": payload})
            future.get(timeout=self._producer.config["request_timeout_ms"] / 1000)
        except Exception as e:
            raise ProviderError(f"Kafka publish failed: {e}") from e
