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
