"""Provider registry + runtime resolution.

Concrete providers register themselves with ``@register(kind, name)``. Scripts
call ``get_provider(kind)`` and get whichever implementation is selected by the
``<KIND>_PROVIDER`` env var (e.g. ``AI_PROVIDER``), falling back to a default.
Adding a provider is drop-in: implement the interface, decorate it, import it
in ``scripts/providers/__init__.py``.
"""

import os

from scripts.providers.base import ProviderError

# (kind, name) -> provider class
_REGISTRY: dict[tuple[str, str], type] = {}
# (kind, name) -> instantiated provider (providers are stateless + reusable)
_INSTANCES: dict[tuple[str, str], object] = {}

# Default provider per kind when <KIND>_PROVIDER is unset.
DEFAULTS: dict[str, str] = {
    "ai": "claude",
    "audio": "elevenlabs",
    "video": "heygen",
}


def register(kind: str, name: str):
    """Class decorator that registers a provider under (kind, name)."""

    def decorator(cls: type) -> type:
        _REGISTRY[(kind, name)] = cls
        return cls

    return decorator


def get_provider(kind: str, name: str | None = None):
    """Resolve and return the provider for ``kind``.

    Selection order: explicit ``name`` arg, then ``<KIND>_PROVIDER`` env var,
    then the built-in default. Instances are cached per (kind, name).
    """
    name = name or os.getenv(f"{kind.upper()}_PROVIDER", "") or DEFAULTS.get(kind, "")
    key = (kind, name)

    if key in _INSTANCES:
        return _INSTANCES[key]

    cls = _REGISTRY.get(key)
    if cls is None:
        known = [n for (k, n) in _REGISTRY if k == kind] or ["none"]
        raise ProviderError(
            f"No {kind} provider registered as '{name}'. Known {kind} providers: {known}."
        )

    instance = cls()
    _INSTANCES[key] = instance
    return instance
