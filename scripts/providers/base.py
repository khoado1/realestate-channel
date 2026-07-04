"""Provider interfaces shared across the content pipeline.

Each capability the pipeline consumes (AI text, audio synthesis, video
generation) has one abstract interface here. Concrete API providers implement
the relevant interface and self-register (see ``registry``), so a script asks
for a *kind* and gets whichever provider is configured at runtime.
"""

from abc import ABC, abstractmethod
from pathlib import Path


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


class AudioProvider(ABC):
    """Text-to-speech / audio synthesis."""

    @abstractmethod
    def synthesize(self, text: str, voice_id: str, out_path: Path, *, timeout: int = 120) -> int:
        """Generate speech for ``text`` and stream it to ``out_path``.

        Returns the number of bytes written. Raises ``ProviderError`` on failure.
        """

    @abstractmethod
    def list_voices(self) -> list[dict]:
        """Return available voices. Raises ``ProviderError`` on failure."""

    @abstractmethod
    def usage(self) -> dict:
        """Return usage/credit info (used, limit, remaining, pct_used).

        Raises ``ProviderError`` on failure.
        """
