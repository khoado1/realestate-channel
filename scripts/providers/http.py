"""Shared HTTP boundary for providers.

All provider API calls funnel through here so error handling is uniform and
there is a single seam for recording calls. Phase 3's call store registers a
recorder via ``set_recorder``; until then the recorder is a no-op and nothing
is persisted.
"""

import time
from typing import Any, Callable

from scripts.providers.base import ProviderError

# Phase 3 replaces this with the call store's recorder. Signature: (dict) -> None.
_recorder: Callable[[dict], None] | None = None


def set_recorder(fn: Callable[[dict], None] | None) -> None:
    """Install (or clear) the call recorder invoked after every request."""
    global _recorder
    _recorder = fn


def _record(entry: dict) -> None:
    if _recorder is None:
        return
    try:
        _recorder(entry)
    except Exception:
        # Recording must never break the primary call flow.
        pass


def request_json(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json: Any = None,
    params: dict | None = None,
    timeout: int = 60,
) -> dict:
    """Make a JSON request, returning parsed JSON. Raises ProviderError on failure."""
    import requests

    started = time.time()
    status = resp = None
    error = None
    try:
        resp = requests.request(
            method.upper(), url, headers=headers, json=json, params=params, timeout=timeout
        )
        status = resp.status_code
        resp.raise_for_status()
        data = resp.json()
        return data
    except requests.exceptions.HTTPError as exc:
        body = resp.text[:300] if resp is not None else ""
        error = f"HTTP {status}: {body}"
        raise ProviderError(error) from exc
    except requests.exceptions.RequestException as exc:
        error = str(exc)
        raise ProviderError(error) from exc
    finally:
        _record(
            {
                "method": method.upper(),
                "url": url,
                "params": params,
                "request": json,
                "http_status": status,
                "error": error,
                "latency_ms": int((time.time() - started) * 1000),
            }
        )
