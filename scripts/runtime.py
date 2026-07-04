import os
from typing import Callable

from dotenv import load_dotenv

from scripts.utils.path_utils import resolve

# ── Project layout catalog ────────────────────────────────────────────────────
# Directory env vars whose default is derived from BASE_CONTENT_DIR. The default
# subdir lives here once so every script shares the same layout instead of each
# re-declaring `os.path.join(content_dir, "...")`. An env var of the same name
# still overrides the derived default at resolution time.
CONTENT_SUBDIRS: dict[str, str] = {
    "SCRIPTS_DIR":    "scripts",
    "IDEAS_DIR":      "ideas",
    "ANALYTICS_DIR":  "analytics",
    "REPURPOSED_DIR": "repurposed",
    "DATA_DIR":       ".data",   # call store (sqlite + artifacts)
}

# Path env vars with no content-relative default — resolved straight from the
# environment (empty string when unset).
ENV_ONLY_PATHS: set[str] = {"VIDEO_DIR", "AUDIO_DIR", "LONGFORM_DIR", "SHORTS_DIR"}

# Shared defaults for non-path environment values.
ENV_DEFAULTS: dict[str, str] = {
    "CHANNEL_NAME": "realestate-channel",
    "ELEVENLABS_FALLBACK_VOICE_ID": "21m00Tcm4TlvDq8ikWAM",  # Rachel (ElevenLabs default)
}


PathSpec = tuple[str, "str | Callable[[str], str]"]
EnvSpec = tuple["str | tuple[str, ...]", str]


def init_environment() -> None:
    """Load environment variables from the local .env file when present."""
    load_dotenv()


def resolve_env_path(name: str, default: str = "") -> str:
    """Resolve an environment-variable path using the shared path utility."""
    return resolve(os.getenv(name, default))


class RuntimeConfig:
    """Encapsulate script runtime configuration and environment resolution.

    Scripts declare *what* they need by name via ``paths`` and ``env``; the
    *defaults* come from the shared catalog above. Pass ``path_specs`` /
    ``env_specs`` for one-off values the catalog doesn't know about.
    """

    def __init__(
        self,
        *,
        paths: list[str] | None = None,
        env: list[str | tuple[str, ...]] | None = None,
        path_specs: list[PathSpec] | None = None,
        env_specs: list[EnvSpec] | None = None,
    ) -> None:
        self.path_specs = self._catalog_path_specs(paths) + list(path_specs or [])
        self.env_specs = self._catalog_env_specs(env) + list(env_specs or [])
        self._initialize()

    @staticmethod
    def _catalog_path_specs(paths: list[str] | None) -> list[PathSpec]:
        """Resolve catalog path names to (name, spec) pairs."""
        specs: list[PathSpec] = []
        for name in paths or []:
            if name in CONTENT_SUBDIRS:
                subdir = CONTENT_SUBDIRS[name]
                specs.append((name, lambda content_dir, s=subdir: os.path.join(content_dir, s)))
            elif name in ENV_ONLY_PATHS:
                specs.append((name, ""))
            else:
                raise KeyError(
                    f"Unknown path '{name}'. Add it to CONTENT_SUBDIRS or ENV_ONLY_PATHS "
                    f"in scripts/runtime.py, or pass an explicit (name, spec) via path_specs."
                )
        return specs

    @staticmethod
    def _catalog_env_specs(env: list[str | tuple[str, ...]] | None) -> list[EnvSpec]:
        """Resolve catalog env entries to (name-or-fallbacks, default) pairs."""
        specs: list[EnvSpec] = []
        for entry in env or []:
            primary = entry if isinstance(entry, str) else entry[0]
            specs.append((entry, ENV_DEFAULTS.get(primary, "")))
        return specs

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
