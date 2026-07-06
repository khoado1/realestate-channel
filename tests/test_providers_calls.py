import pytest

from scripts.providers import calls as calls_module
from scripts.providers.base import ProviderError
from scripts.providers.calls import call_ai, youtube_get


class FakeAIProvider:
    def __init__(self, *, result=None, error=None):
        self._result = result
        self._error = error

    def complete(self, prompt, *, system=None, max_tokens=1000, timeout=60):
        if self._error is not None:
            raise self._error
        return self._result


def patch_provider(monkeypatch, provider):
    monkeypatch.setattr(calls_module, "get_provider", lambda kind: provider)


def test_call_ai_returns_provider_completion(monkeypatch):
    patch_provider(monkeypatch, FakeAIProvider(result="the response text"))
    result = call_ai("research", "some prompt", channel_name="Real Estate with AI")
    assert result == "the response text"


def test_call_ai_on_error_raise_propagates_provider_error(monkeypatch):
    patch_provider(monkeypatch, FakeAIProvider(error=ProviderError("api down")))
    with pytest.raises(ProviderError):
        call_ai("research", "some prompt", channel_name="Real Estate with AI", on_error="raise")


def test_call_ai_on_error_exit_calls_sys_exit(monkeypatch):
    patch_provider(monkeypatch, FakeAIProvider(error=ProviderError("api down")))
    with pytest.raises(SystemExit) as exc_info:
        call_ai("research", "some prompt", channel_name="Real Estate with AI", on_error="exit")
    assert exc_info.value.code == 1


def test_call_ai_on_error_placeholder_returns_bracketed_message(monkeypatch):
    patch_provider(monkeypatch, FakeAIProvider(error=ProviderError("api down")))
    result = call_ai("research", "some prompt", channel_name="Real Estate with AI", on_error="placeholder")
    assert result == "[research insight unavailable: api down]"


def test_call_ai_placeholder_also_catches_non_provider_errors(monkeypatch):
    patch_provider(monkeypatch, FakeAIProvider(error=ValueError("unexpected")))
    result = call_ai("research", "some prompt", channel_name="Real Estate with AI", on_error="placeholder")
    assert result == "[research insight unavailable: unexpected]"


def test_call_ai_on_error_exit_still_propagates_non_provider_errors(monkeypatch):
    """Only ProviderError gets the on_error UX — anything else propagates as-is,
    even when on_error='exit' asked for a fatal sys.exit."""
    patch_provider(monkeypatch, FakeAIProvider(error=ValueError("unexpected")))
    with pytest.raises(ValueError):
        call_ai("research", "some prompt", channel_name="Real Estate with AI", on_error="exit")


def test_youtube_get_builds_url_and_merges_api_key(monkeypatch):
    captured = {}

    def fake_request_json(method, url, *, params=None, timeout=60):
        captured["method"] = method
        captured["url"] = url
        captured["params"] = params
        return {"items": []}

    monkeypatch.setattr(calls_module.provider_http, "request_json", fake_request_json)

    result = youtube_get("search", {"q": "arm loans"}, api_key="secret-key")

    assert result == {"items": []}
    assert captured["method"] == "GET"
    assert captured["url"] == "https://www.googleapis.com/youtube/v3/search"
    assert captured["params"] == {"q": "arm loans", "key": "secret-key"}
