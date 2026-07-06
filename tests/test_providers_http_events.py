import requests as requests_lib

from scripts.providers import http as http_module


def make_response(status_code=200, json_body=None):
    resp = requests_lib.Response()
    resp.status_code = status_code
    resp._content = b"{}" if json_body is None else __import__("json").dumps(json_body).encode()
    return resp


def test_request_json_publishes_provider_call_completed_event(monkeypatch):
    published = []
    monkeypatch.setattr(http_module, "publish_event", lambda event, payload: published.append((event, payload)))
    monkeypatch.setattr(http_module, "send", lambda *a, **k: make_response(200, {"ok": True}))

    with http_module.call_context(provider="youtube", kind="data", operation="search"):
        result = http_module.request_json("GET", "https://api.example.com/v1/search")

    assert result == {"ok": True}
    assert len(published) == 1
    event, payload = published[0]
    assert event == "provider.call.completed"
    assert payload["provider"] == "youtube"
    assert payload["operation"] == "search"
    assert payload["http_status"] == 200
    assert payload["error"] is None


def test_request_json_publishes_event_even_on_http_error(monkeypatch):
    published = []
    monkeypatch.setattr(http_module, "publish_event", lambda event, payload: published.append((event, payload)))
    monkeypatch.setattr(http_module, "send", lambda *a, **k: make_response(500))

    try:
        http_module.request_json("GET", "https://api.example.com/v1/search")
        assert False, "expected ProviderError"
    except http_module.ProviderError:
        pass

    assert len(published) == 1
    event, payload = published[0]
    assert event == "provider.call.completed"
    assert payload["http_status"] == 500
    assert payload["error"] is not None


def test_event_publish_failure_does_not_break_the_call(monkeypatch):
    """request_json relies on publish_event() to never raise, even when the
    configured events provider itself is broken — verify the call still
    succeeds using the real (unmocked) publish_event, not a stand-in."""
    from scripts.providers import events as events_module

    def broken_get_provider(kind):
        raise RuntimeError("events provider misconfigured")

    monkeypatch.setattr(events_module, "get_provider", broken_get_provider)
    monkeypatch.setattr(http_module, "send", lambda *a, **k: make_response(200, {"ok": True}))

    result = http_module.request_json("GET", "https://api.example.com/v1/search")
    assert result == {"ok": True}
