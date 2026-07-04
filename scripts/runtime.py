import os
from typing import Callable

from dotenv import load_dotenv

from scripts.utils.path_utils import resolve


def init_environment() -> None:
    """Load environment variables from the local .env file when present."""
    load_dotenv()


def resolve_env_path(name: str, default: str = "") -> str:
    """Resolve an environment-variable path using the shared path utility."""
    return resolve(os.getenv(name, default))


class RuntimeConfig:
    """Encapsulate script runtime configuration and environment resolution."""

    def __init__(
        self,
        *,
        path_specs: list[tuple[str, str | Callable[[str], str]]] | None = None,
        env_specs: list[tuple[str | tuple[str, ...], str]] | None = None,
    ) -> None:
        self.path_specs = list(path_specs or [])
        self.env_specs = list(env_specs or [])
        self._initialize()

    def _initialize(self) -> None:
        init_environment()
        self.CONTENT_DIR = resolve_env_path("BASE_CONTENT_DIR", "")

        for name, spec in self.path_specs:
            default = spec(self.CONTENT_DIR) if callable(spec) else spec
            setattr(self, name, resolve_env_path(name, default))

        for name, default in self.env_specs:
            # `name` may be a single var name, or a tuple of fallback names
            # ("PRIMARY", "FALLBACK", ...) resolved to the first one that is set.
            names = (name,) if isinstance(name, str) else tuple(name)
            value = next((v for n in names if (v := os.getenv(n))), default)
            setattr(self, names[0], value)
