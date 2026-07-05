"""Gateway transport: every outbound HTTP call runs through ``send``.

Wraps ``requests`` with a per-host circuit breaker and an exponential-backoff
retry policy (both configured in scripts/config/gateway.toml). Callers get
back a normal ``requests.Response`` on success; failures raise ``GatewayError``
(or ``CircuitOpenError`` if the host's breaker is open).

Calls that create/mutate something server-side (POST, PATCH) also get an
``Idempotency-Key`` header, generated once per logical call and reused across
every retry of that call — so if a provider honors the header, a retry after
an ambiguous failure (e.g. a timeout where the first attempt may have actually
gone through) is deduped server-side instead of creating a second job/charge.
Providers that don't recognize the header just ignore it.
"""

import time
import uuid
from urllib.parse import urlparse

import requests

from scripts.gateway.circuit_breaker import breaker_for
from scripts.gateway.errors import GatewayError
from scripts.gateway.retry import load_retry_policy
from scripts.utils.logging import get_logger

log = get_logger(__name__)

# HTTP methods that create/mutate a resource, where a retried call risks a
# duplicate side effect on the provider's side and so benefits from a stable
# idempotency key. GET/DELETE aren't included: reads have no side effect to
# dedupe, and every provider call in this codebase today is GET or POST/PATCH.
IDEMPOTENT_KEY_METHODS = {"POST", "PATCH"}


def send(method: str, url: str, **kwargs) -> requests.Response:
    """Execute one logical HTTP call with retry + circuit breaker.

    ``kwargs`` are passed straight through to ``requests.request`` (headers,
    json, data, params, timeout, stream, ...).
    """
    host = urlparse(url).netloc
    breaker = breaker_for(host)
    policy = load_retry_policy()

    idempotency_key = None
    if method.upper() in IDEMPOTENT_KEY_METHODS:
        headers = dict(kwargs.get("headers") or {})
        idempotency_key = headers.setdefault("Idempotency-Key", str(uuid.uuid4()))
        kwargs["headers"] = headers

    attempt = 0
    while True:
        attempt += 1
        breaker.before_call()  # raises CircuitOpenError if rejecting calls

        try:
            resp = requests.request(method, url, **kwargs)
        except requests.exceptions.RequestException as exc:
            breaker.record_failure()
            if attempt >= policy.max_attempts:
                log.error(
                    "request failed — retries exhausted",
                    extra={
                        "fields": {
                            "method": method, "host": host, "attempt": attempt,
                            "error": str(exc), "idempotency_key": idempotency_key,
                        }
                    },
                )
                raise GatewayError(f"{method} {url} failed: {exc}") from exc
            delay = policy.delay(attempt)
            log.warning(
                "request failed — retrying",
                extra={
                    "fields": {
                        "method": method, "host": host, "attempt": attempt,
                        "error": str(exc), "retry_in_ms": int(delay * 1000),
                        "idempotency_key": idempotency_key,
                    }
                },
            )
            time.sleep(delay)
            continue

        if policy.is_retryable_status(resp.status_code) and attempt < policy.max_attempts:
            breaker.record_failure()
            delay = policy.delay(attempt)
            log.warning(
                "retryable status — retrying",
                extra={
                    "fields": {
                        "method": method, "host": host, "attempt": attempt,
                        "status": resp.status_code, "retry_in_ms": int(delay * 1000),
                        "idempotency_key": idempotency_key,
                    }
                },
            )
            time.sleep(delay)
            continue

        if resp.status_code >= 500:
            breaker.record_failure()
        else:
            breaker.record_success()
        return resp
