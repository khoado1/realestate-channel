"""Provider interfaces shared across the content pipeline.

Each capability the pipeline consumes (AI text, audio synthesis, video
generation) has one abstract interface here. Concrete API providers implement
the relevant interface and self-register (see ``registry``), so a script asks
for a *kind* and gets whichever provider is configured at runtime.
"""

from abc import ABC, abstractmethod


class ProviderError(Exception):
    """Raised when a provider API call fails (transport, HTTP, or config)."""


class AIProvider(ABC):
    """Text completion / generation from a large language model."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1000,
        timeout: int = 60,
    ) -> str:
        """Return the model's text response for ``prompt``.

        Raises ``ProviderError`` on any failure so callers can choose their own
        UX (fatal exit vs. graceful degradation).
        """
