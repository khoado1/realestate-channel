"""Provider interfaces shared across the content pipeline.

Each capability the pipeline consumes (AI text, audio synthesis, video
generation) has one abstract interface here. Concrete API providers implement
the relevant interface and self-register (see ``registry``), so a script asks
for a *kind* and gets whichever provider is configured at runtime.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
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


@dataclass
class VideoRequest:
    """Caller-supplied inputs for a video render (provider fills in the rest)."""

    audio_path: Path
    title: str
    script_text: str = ""
    audio_asset_id: str = ""


@dataclass
class VideoStatus:
    """Normalized render status across video providers."""

    state: str  # "pending" | "completed" | "failed"
    video_url: str = ""
    error: str = ""


class VideoProvider(ABC):
    """Avatar / animated video generation (async submit + poll)."""

    def upload_audio(self, audio_path: Path) -> str:
        """Upload local audio to the service, returning an asset reference.

        Default: the service does not require pre-hosted audio.
        """
        return ""

    @abstractmethod
    def submit(self, req: VideoRequest) -> str:
        """Submit a render job; return its job id. Raises ``ProviderError``."""

    @abstractmethod
    def status(self, job_id: str) -> VideoStatus:
        """Return the normalized status for ``job_id``. Raises ``ProviderError``."""


class EventPublisher(ABC):
    """Publish domain events (circuit breaker transitions, completed calls,
    backlog writes, ...) to subscribers — console by default, pluggable to an
    external bus like Kafka. A different concern from structured logging
    (scripts/utils/logging.py, machine-readable ops logs) and the call
    recorder (scripts/providers/http.py, persisted call/cost records): this
    is for events a downstream subscriber might react to.
    """

    @abstractmethod
    def publish(self, event: str, payload: dict) -> None:
        """Publish ``event`` with ``payload``. Raises ``ProviderError`` on failure."""
