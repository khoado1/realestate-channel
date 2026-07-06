import pytest

from scripts.gateway import circuit_breaker as cb_module
from scripts.gateway import client as client_module
from scripts.providers import registry as registry_module


@pytest.fixture(autouse=True)
def _reset_circuit_breakers():
    """Circuit breakers are cached per-host at module scope — clear between tests."""
    cb_module._breakers.clear()
    yield
    cb_module._breakers.clear()


@pytest.fixture(autouse=True)
def _reset_gateway_event_sink():
    """The event sink is process-global — clear it so tests don't leak into each other."""
    cb_module.set_event_sink(None)
    yield
    cb_module.set_event_sink(None)


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Retry backoff sleeps for real seconds — skip it so retry tests run instantly."""
    monkeypatch.setattr(client_module.time, "sleep", lambda seconds: None)


@pytest.fixture(autouse=True)
def _reset_provider_instances():
    """Provider instances are cached per (kind, name) at module scope — clear
    between tests so a provider constructed under one test's monkeypatches
    (e.g. a fake KafkaProducer) doesn't leak into another test."""
    registry_module._INSTANCES.clear()
    yield
    registry_module._INSTANCES.clear()
