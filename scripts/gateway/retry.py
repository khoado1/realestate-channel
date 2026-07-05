"""Exponential backoff retry policy, tuned via scripts/config/gateway.toml."""

import random
from dataclasses import dataclass, field

from scripts.utils.config import load


@dataclass
class RetryPolicy:
    max_attempts: int
    base_delay: float
    max_delay: float
    jitter: float
    retry_status_codes: set[int] = field(default_factory=set)

    def is_retryable_status(self, status_code: int) -> bool:
        return status_code in self.retry_status_codes

    def delay(self, attempt: int) -> float:
        """Backoff before retrying ``attempt`` (1 = first retry), with jitter."""
        raw = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        spread = raw * self.jitter
        return max(0.0, raw + random.uniform(-spread, spread))


def load_retry_policy() -> RetryPolicy:
    cfg = load("gateway")["retry"]
    return RetryPolicy(
        max_attempts=cfg["max_attempts"],
        base_delay=cfg["base_delay"],
        max_delay=cfg["max_delay"],
        jitter=cfg["jitter"],
        retry_status_codes=set(cfg["retry_status_codes"]),
    )
