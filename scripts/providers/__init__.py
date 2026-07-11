"""AI/audio/video provider plugins.

Import concrete providers here so their ``@register`` decorators run when the
package is imported.
"""

from scripts.providers.base import (  # noqa: F401
    AIProvider,
    AudioProvider,
    ProviderError,
    VideoProvider,
    VideoRequest,
    VideoStatus,
)
from scripts.providers.registry import get_provider, register  # noqa: F401

# Concrete providers (registration side effects):
from scripts.providers import claude  # noqa: F401,E402
from scripts.providers import elevenlabs  # noqa: F401,E402
from scripts.providers import heygen  # noqa: F401,E402
from scripts.providers import hyperframes  # noqa: F401,E402
from scripts.providers import console_events  # noqa: F401,E402
from scripts.providers import kafka_events  # noqa: F401,E402

# Auto-enable call logging (unless CALL_LOG=0). Lazy import keeps `http` free of
# any dependency on the store; the DB is created on first recorded call.
try:  # pragma: no cover - best-effort wiring
    import os as _os

    if _os.getenv("CALL_LOG", "1") != "0":
        from scripts.store import enable as _enable_store

        _enable_store()
except Exception:
    pass

# Wire the gateway's circuit-breaker transitions into the events provider
# (unless EVENTS_LOG=0). Lazy import keeps `scripts.gateway` free of any
# dependency on the providers layer above it.
try:  # pragma: no cover - best-effort wiring
    from scripts.providers.events import wire_gateway_events as _wire_gateway_events

    _wire_gateway_events()
except Exception:
    pass
