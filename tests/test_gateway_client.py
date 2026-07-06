import requests as requests_lib

from scripts.gateway import client as client_module
from scripts.gateway.circuit_breaker import OPEN
from scripts.gateway.client import send
from scripts.gateway.errors import CircuitOpenError, GatewayError


def make_response(status_code=200):
    resp = requests_lib.Response()
    resp.status_code = status_code
    return resp


def test_success_on_first_attempt(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return make_response(200)

    monkeypatch.setattr(client_module.requests, "request", fake_request)
    resp = send("GET", "https://api.example.com/v1/thing")
    assert resp.status_code == 200
    assert len(calls) == 1


def test_retries_transient_transport_error_then_succeeds(monkeypatch):
    attempts = {"n": 0}

    def fake_request(method, url, **kwargs):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise requests_lib.exceptions.ConnectionError("boom")
        return make_response(200)

    monkeypatch.setattr(client_module.requests, "request", fake_request)
    resp = send("GET", "https://retry-host.example.com/v1/thing")
    assert resp.status_code == 200
    assert attempts["n"] == 2


def test_exhausts_retries_and_raises_gateway_error(monkeypatch):
    attempts = {"n": 0}

    def fake_request(method, url, **kwargs):
        attempts["n"] += 1
        raise requests_lib.exceptions.ConnectionError("still down")

    monkeypatch.setattr(client_module.requests, "request", fake_request)
    try:
        send("GET", "https://always-down.example.com/v1/thing")
        assert False, "expected GatewayError"
    except GatewayError:
        pass
    # gateway.toml: max_attempts = 3
    assert attempts["n"] == 3


def test_retries_retryable_status_code_then_succeeds(monkeypatch):
    statuses = [503, 200]

    def fake_request(method, url, **kwargs):
        return make_response(statuses.pop(0))

    monkeypatch.setattr(client_module.requests, "request", fake_request)
    resp = send("GET", "https://flaky-host.example.com/v1/thing")
    assert resp.status_code == 200


def test_idempotency_key_stable_across_retries_on_post(monkeypatch):
    seen_keys = []

    def fake_request(method, url, **kwargs):
        seen_keys.append(kwargs["headers"]["Idempotency-Key"])
        if len(seen_keys) < 2:
            raise requests_lib.exceptions.ConnectionError("boom")
        return make_response(200)

    monkeypatch.setattr(client_module.requests, "request", fake_request)
    send("POST", "https://idempotent-host.example.com/v1/jobs")
    assert len(seen_keys) == 2
    assert seen_keys[0] == seen_keys[1]


def test_get_does_not_get_idempotency_key(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return make_response(200)

    monkeypatch.setattr(client_module.requests, "request", fake_request)
    send("GET", "https://no-key-host.example.com/v1/thing")
    assert not captured["headers"] or "Idempotency-Key" not in captured["headers"]


def test_circuit_opens_and_short_circuits_further_calls(monkeypatch):
    host = "breaker-host.example.com"

    def fake_request(method, url, **kwargs):
        raise requests_lib.exceptions.ConnectionError("down")

    monkeypatch.setattr(client_module.requests, "request", fake_request)

    # gateway.toml: failure_threshold = 5, max_attempts = 3. The first send()
    # exhausts 3 attempts (3 failures) and raises GatewayError. The second
    # send()'s 2nd attempt is the 5th failure overall, tripping the breaker
    # open mid-retry — its 3rd attempt is short-circuited as CircuitOpenError
    # (also a GatewayError) instead of making a 6th real request.
    for _ in range(2):
        try:
            send("GET", f"https://{host}/v1/thing")
        except GatewayError:
            pass

    from scripts.gateway.circuit_breaker import breaker_for

    assert breaker_for(host).state == OPEN

    calls_before = 0

    def counting_request(method, url, **kwargs):
        nonlocal calls_before
        calls_before += 1
        raise requests_lib.exceptions.ConnectionError("down")

    monkeypatch.setattr(client_module.requests, "request", counting_request)

    try:
        send("GET", f"https://{host}/v1/thing")
        assert False, "expected CircuitOpenError"
    except CircuitOpenError:
        pass
    assert calls_before == 0  # rejected before any request was attempted
