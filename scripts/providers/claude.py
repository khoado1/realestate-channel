"""Anthropic Claude — AI provider."""

import os

from scripts.providers import http
from scripts.providers.base import AIProvider, ProviderError
from scripts.providers.registry import register

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
# TODO(Phase 4): move the model id into declarative provider config.
MODEL = "claude-sonnet-4-20250514"


@register("ai", "claude")
class ClaudeProvider(AIProvider):
    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1000,
        timeout: int = 60,
    ) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ProviderError("ANTHROPIC_API_KEY not set in .env")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        payload: dict = {
            "model": MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        with http.call_context(provider="claude", kind="ai", operation="complete", model=MODEL):
            data = http.request_json("POST", API_URL, headers=headers, json=payload, timeout=timeout)
        return "\n".join(
            b["text"] for b in data.get("content", []) if b.get("type") == "text"
        )
