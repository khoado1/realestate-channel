import sys
import types

import pytest

from scripts.gateway import circuit_breaker as cb_module
from scripts.providers import events as events_module
from scripts.providers.base import ProviderError
from scripts.providers.console_events import ConsolePublisher
from scripts.providers.kafka_events import KafkaPublisher


def test_console_publisher_prints_event_and_payload(capsys):
    ConsolePublisher().publish("backlog.appended", {"source": "research"})
    out = capsys.readouterr().out
    assert "backlog.appended" in out
    assert "research" in out


def test_publish_event_uses_configured_provider(monkeypatch):
    seen = []
    monkeypatch.setattr(events_module, "get_provider", lambda kind: types.SimpleNamespace(
        publish=lambda event, payload: seen.append((event, payload))
    ))
    events_module.publish_event("circuit.open", {"host": "example.com"})
    assert seen == [("circuit.open", {"host": "example.com"})]


def test_publish_event_swallows_and_logs_provider_failures(monkeypatch):
    def boom(kind):
        raise ProviderError("no subscriber configured")

    monkeypatch.setattr(events_module, "get_provider", boom)
    # must not raise — a broken/unconfigured event subscriber can't break the caller
    events_module.publish_event("circuit.open", {"host": "example.com"})


def test_wire_gateway_events_installs_sink(monkeypatch):
    monkeypatch.setenv("EVENTS_LOG", "1")
    events_module.wire_gateway_events()
    assert cb_module._event_sink is events_module.publish_event


def test_wire_gateway_events_respects_events_log_off(monkeypatch):
    monkeypatch.setenv("EVENTS_LOG", "0")
    cb_module.set_event_sink(None)
    events_module.wire_gateway_events()
    assert cb_module._event_sink is None


class FakeFuture:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def get(self, timeout=None):
        if self._error:
            raise self._error
        return self._result


class FakeKafkaProducer:
    """Stand-in for kafka.KafkaProducer — records constructor args and sent messages."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.config = {"request_timeout_ms": kwargs.get("request_timeout_ms", 5000)}
        self.sent = []
        FakeKafkaProducer.instances.append(self)

    def send(self, topic, value):
        self.sent.append((topic, value))
        return FakeFuture(result="ok")


@pytest.fixture
def fake_kafka_module(monkeypatch):
    FakeKafkaProducer.instances = []
    fake_module = types.ModuleType("kafka")
    fake_module.KafkaProducer = FakeKafkaProducer
    monkeypatch.setitem(sys.modules, "kafka", fake_module)
    yield FakeKafkaProducer


def test_kafka_publisher_constructs_producer_from_config(fake_kafka_module):
    publisher = KafkaPublisher()
    producer = fake_kafka_module.instances[0]
    assert producer.kwargs["bootstrap_servers"] == ["localhost:9092"]
    assert producer.kwargs["api_version"] == (2, 0, 0)
    assert publisher._topic == "realestate-channel.events"


def test_kafka_publisher_publish_sends_event_and_payload(fake_kafka_module):
    publisher = KafkaPublisher()
    publisher.publish("backlog.appended", {"source": "research"})
    producer = fake_kafka_module.instances[0]
    topic, value = producer.sent[0]
    assert topic == "realestate-channel.events"
    assert value == {"event": "backlog.appended", "payload": {"source": "research"}}


def test_kafka_publisher_wraps_send_failure_as_provider_error(fake_kafka_module):
    publisher = KafkaPublisher()
    producer = fake_kafka_module.instances[0]
    producer.send = lambda topic, value: FakeFuture(error=RuntimeError("broker unreachable"))
    with pytest.raises(ProviderError):
        publisher.publish("backlog.appended", {"source": "research"})


def test_kafka_publisher_raises_provider_error_when_kafka_not_installed(monkeypatch):
    monkeypatch.setitem(sys.modules, "kafka", None)
    with pytest.raises(ProviderError):
        KafkaPublisher()
