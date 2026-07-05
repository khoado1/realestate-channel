"""API gateway — the transport layer every outbound HTTP call runs through.

Cloud-native call resilience (retry with exponential backoff, per-host circuit
breaking) lives here, separate from ``scripts.providers.http``, which owns
response parsing and call recording. Providers, and any script making a raw
API call (e.g. the YouTube Data API), should call ``send`` instead of
``requests`` directly so every outbound call gets the same resilience.
"""

from scripts.gateway.client import send  # noqa: F401
from scripts.gateway.errors import CircuitOpenError, GatewayError  # noqa: F401
