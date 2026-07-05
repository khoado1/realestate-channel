"""Per-host circuit breaker, tuned via scripts/config/gateway.toml.

Closed → Open after ``failure_threshold`` consecutive failures. Open calls are
rejected until ``reset_timeout`` elapses, then one trial (half-open) call is
allowed through; it closes the circuit on success or reopens it on failure.
"""

import time

from scripts.gateway.errors import CircuitOpenError
from scripts.utils.config import load
from scripts.utils.logging import get_logger

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"

log = get_logger(__name__)


class CircuitBreaker:
    def __init__(self, host: str, failure_threshold: int, reset_timeout: float, half_open_max_calls: int):
        self.host = host
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        self.state = CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self.half_open_calls = 0

    def before_call(self) -> None:
        """Raise ``CircuitOpenError`` if a call to this host should be rejected."""
        if self.state == OPEN:
            if time.time() - self.opened_at < self.reset_timeout:
                log.debug("circuit call rejected", extra={"fields": {"host": self.host, "state": self.state}})
                raise CircuitOpenError(f"circuit open for {self.host} — retry after cooldown")
            self.state = HALF_OPEN
            self.half_open_calls = 0
            log.info("circuit half-open — trial call", extra={"fields": {"host": self.host}})

        if self.state == HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                log.debug("circuit call rejected", extra={"fields": {"host": self.host, "state": self.state}})
                raise CircuitOpenError(f"circuit half-open for {self.host} — trial call in flight")
            self.half_open_calls += 1

    def record_success(self) -> None:
        if self.state != CLOSED:
            log.info("circuit closed — recovered", extra={"fields": {"host": self.host}})
        self.state = CLOSED
        self.failures = 0

    def record_failure(self) -> None:
        self.failures += 1
        if self.state != OPEN and (self.state == HALF_OPEN or self.failures >= self.failure_threshold):
            self.state = OPEN
            self.opened_at = time.time()
            log.warning(
                "circuit open",
                extra={"fields": {"host": self.host, "failures": self.failures}},
            )


_breakers: dict[str, CircuitBreaker] = {}


def breaker_for(host: str) -> CircuitBreaker:
    """Return the (lazily created) circuit breaker for ``host``."""
    if host not in _breakers:
        cfg = load("gateway")["circuit_breaker"]
        _breakers[host] = CircuitBreaker(
            host=host,
            failure_threshold=cfg["failure_threshold"],
            reset_timeout=cfg["reset_timeout"],
            half_open_max_calls=cfg["half_open_max_calls"],
        )
    return _breakers[host]
