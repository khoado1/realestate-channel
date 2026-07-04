"""AI/audio/video provider plugins.

Import concrete providers here so their ``@register`` decorators run when the
package is imported.
"""

from scripts.providers.base import AIProvider, AudioProvider, ProviderError  # noqa: F401
from scripts.providers.registry import get_provider, register  # noqa: F401

# Concrete providers (registration side effects):
from scripts.providers import claude  # noqa: F401,E402
from scripts.providers import elevenlabs  # noqa: F401,E402
