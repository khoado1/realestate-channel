"""Gateway-level errors.

Kept independent of ``scripts.providers`` (which depends on the gateway, not
the other way around) so the gateway stays usable by non-provider callers.
"""


class GatewayError(Exception):
    """Raised when a request fails after exhausting retries, or transport-fails."""


class CircuitOpenError(GatewayError):
    """Raised when a host's circuit breaker is open and rejecting calls."""
