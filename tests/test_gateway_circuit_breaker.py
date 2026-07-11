import pytest

from scripts.gateway import circuit_breaker as cb_module
from scripts.gateway.circuit_breaker import CLOSED, HALF_OPEN, OPEN, CircuitBreaker
from scripts.gateway.errors import CircuitOpenError


def make_breaker(failure_threshold=3, reset_timeout=30.0, half_open_max_calls=1):
    return CircuitBreaker(
        host="api.example.com",
        failure_threshold=failure_threshold,
        reset_timeout=reset_timeout,
        half_open_max_calls=half_open_max_calls,
    )


def test_starts_closed_and_allows_calls():
    breaker = make_breaker()
    assert breaker.state == CLOSED
    breaker.before_call()  # should not raise


def test_opens_after_failure_threshold_consecutive_failures():
    breaker = make_breaker(failure_threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CLOSED
    breaker.record_failure()  # third consecutive failure trips it
    assert breaker.state == OPEN


def test_open_circuit_rejects_calls_immediately():
    breaker = make_breaker(failure_threshold=1)
    breaker.record_failure()
    assert breaker.state == OPEN
    with pytest.raises(CircuitOpenError):
        breaker.before_call()


def test_success_resets_failure_count_without_tripping(monkeypatch):
    breaker = make_breaker(failure_threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    assert breaker.state == CLOSED
    assert breaker.failures == 0
    # two more failures shouldn't trip it — the count was reset, not just capped
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CLOSED


def test_half_open_trial_after_reset_timeout(monkeypatch):
    breaker = make_breaker(failure_threshold=1, reset_timeout=30.0, half_open_max_calls=1)
    breaker.record_failure()
    assert breaker.state == OPEN

    fake_time = [breaker.opened_at]
    monkeypatch.setattr(
        "scripts.gateway.circuit_breaker.time.time", lambda: fake_time[0]
    )

    # still within cooldown -> still rejects
    fake_time[0] = breaker.opened_at + 10
    with pytest.raises(CircuitOpenError):
        breaker.before_call()
    assert breaker.state == OPEN

    # cooldown elapsed -> transitions to half-open and allows the trial call
    fake_time[0] = breaker.opened_at + 31
    breaker.before_call()
    assert breaker.state == HALF_OPEN

    # a second concurrent call while the trial is in flight is rejected
    with pytest.raises(CircuitOpenError):
        breaker.before_call()


def test_half_open_success_closes_circuit(monkeypatch):
    breaker = make_breaker(failure_threshold=1, reset_timeout=30.0)
    breaker.record_failure()
    monkeypatch.setattr(
        "scripts.gateway.circuit_breaker.time.time", lambda: breaker.opened_at + 31
    )
    breaker.before_call()
    assert breaker.state == HALF_OPEN
    breaker.record_success()
    assert breaker.state == CLOSED
    assert breaker.failures == 0


def test_half_open_failure_reopens_circuit(monkeypatch):
    breaker = make_breaker(failure_threshold=1, reset_timeout=30.0)
    breaker.record_failure()
    monkeypatch.setattr(
        "scripts.gateway.circuit_breaker.time.time", lambda: breaker.opened_at + 31
    )
    breaker.before_call()
    assert breaker.state == HALF_OPEN
    breaker.record_failure()
    assert breaker.state == OPEN


def test_event_sink_fires_on_open_half_open_and_closed(monkeypatch):
    events = []
    cb_module.set_event_sink(lambda event, payload: events.append((event, payload)))

    breaker = make_breaker(failure_threshold=1, reset_timeout=30.0)
    breaker.record_failure()  # closed -> open
    monkeypatch.setattr(
        "scripts.gateway.circuit_breaker.time.time", lambda: breaker.opened_at + 31
    )
    breaker.before_call()  # open -> half-open
    breaker.record_success()  # half-open -> closed

    names = [event for event, _ in events]
    assert names == ["circuit.open", "circuit.half_open", "circuit.closed"]
    assert events[0][1] == {"host": breaker.host, "failures": 1}
    assert events[1][1] == {"host": breaker.host}
    assert events[2][1] == {"host": breaker.host}


def test_no_event_sink_installed_is_a_no_op():
    # default state (conftest resets the sink to None) — must not raise
    breaker = make_breaker(failure_threshold=1)
    breaker.record_failure()
    assert breaker.state == OPEN


def test_event_sink_exceptions_are_swallowed():
    def broken_sink(event, payload):
        raise RuntimeError("subscriber exploded")

    cb_module.set_event_sink(broken_sink)
    breaker = make_breaker(failure_threshold=1)
    breaker.record_failure()  # must not raise despite the broken sink
    assert breaker.state == OPEN
