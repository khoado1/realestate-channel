"""Shared call helpers for lightweight API integrations.

Unlike the registered AI/audio/video providers (scripts/providers/claude.py,
elevenlabs.py, ...), the calls here have no swappable implementation to
select at runtime — they either wrap the provider registry itself
(``call_ai``, parametrized per script via ``name``) or talk to a
single-vendor API with no alternative (``youtube_get``). Both still funnel
through scripts.providers.http, so they get the same recording and
retry/circuit-breaker resilience as every registered provider.
"""

import sys
from typing import Literal

from scripts.providers import http as provider_http
from scripts.providers.base import ProviderError
from scripts.providers.registry import get_provider
from scripts.utils.config import load
from scripts.utils.prompts import build_system_prompt

_YOUTUBE_BASE_URL = load("providers")["youtube"]["base_url"]

OnError = Literal["raise", "exit", "placeholder"]


def call_ai(
    name: str,
    prompt: str,
    *,
    channel_name: str,
    max_tokens: int = 1000,
    timeout: int = 60,
    on_error: OnError = "raise",
) -> str:
    """Call the configured AI provider using the prompts.toml section ``name``.

    ``on_error`` picks the failure UX, since scripts differ here:
    - "raise": propagate ``ProviderError`` — caller decides
    - "exit": print and ``sys.exit(1)`` — a broken script run should stop
    - "placeholder": return a bracketed message — used where one failed call
      (e.g. an analytics insight) shouldn't break the rest of a report
    """
    system = build_system_prompt(name, channel_name)
    try:
        return get_provider("ai").complete(prompt, system=system, max_tokens=max_tokens, timeout=timeout)
    except Exception as e:
        if on_error == "placeholder":
            return f"[{name} insight unavailable: {e}]"
        if not isinstance(e, ProviderError):
            raise
        if on_error == "exit":
            print(f"✗ Claude API error: {e}")
            sys.exit(1)
        raise


def youtube_get(endpoint: str, params: dict, *, api_key: str, timeout: int = 15) -> dict:
    """GET a YouTube Data API v3 endpoint. Raises ``ProviderError`` on failure."""
    url = f"{_YOUTUBE_BASE_URL}/{endpoint}"
    with provider_http.call_context(provider="youtube", kind="data", operation=endpoint):
        return provider_http.request_json("GET", url, params={**params, "key": api_key}, timeout=timeout)
