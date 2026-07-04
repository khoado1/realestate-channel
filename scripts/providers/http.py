"""Shared HTTP boundary for providers.

All provider API calls funnel through here so error handling is uniform and
there is a single seam for recording calls. Phase 3's call store registers a
recorder via ``set_recorder``; until then the recorder is a no-op and nothing
is persisted.
"""

import contextvars
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from scripts.providers.base import ProviderError

# The call store installs its recorder here. Signature: (dict) -> None.
_recorder: Callable[[dict], None] | None = None

# Per-call metadata (provider/kind/operation/model) set by providers around a
# call and merged into the record — keeps this module generic.
_ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("call_ctx", default={})


def set_recorder(fn: Callable[[dict], None] | None) -> None:
    """Install (or clear) the call recorder invoked after every request."""
    global _recorder
    _recorder = fn


@contextmanager
def call_context(**meta):
    """Annotate calls made within this block (provider, kind, operation, model)."""
    token = _ctx.set({**_ctx.get(), **meta})
    try:
        yield
    finally:
        _ctx.reset(token)


def _record(entry: dict) -> None:
    if _recorder is None:
        return
    try:
        _recorder({**_ctx.get(), **entry})
    except Exception:
        # Recording must never break the primary call flow.
        pass


def request_json(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json: Any = None,
    data: Any = None,
    params: dict | None = None,
    timeout: int = 60,
) -> dict:
    """Make a request returning parsed JSON. Raises ProviderError on failure.

    ``json`` sends a JSON body; ``data`` sends a raw body (e.g. binary upload).
    """
    import requests

    started = time.time()
    status = resp = response = None
    error = None
    try:
        resp = requests.request(
            method.upper(), url, headers=headers, json=json, data=data, params=params, timeout=timeout
        )
        status = resp.status_code
        resp.raise_for_status()
        response = resp.json()
        return response
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
                "request": json,  # JSON body only; raw `data=` bodies are binary (not recorded)
                "response": response,
                "http_status": status,
                "error": error,
                "latency_ms": int((time.time() - started) * 1000),
            }
        )


def stream_to_file(
    method: str,
    url: str,
    out_path: Path,
    *,
    headers: dict | None = None,
    json: Any = None,
    timeout: int = 120,
    chunk_size: int = 8192,
) -> int:
    """Stream a response body to ``out_path``. Returns bytes written. Raises ProviderError."""
    import requests

    started = time.time()
    status = resp = None
    error = None
    written = 0
    try:
        resp = requests.request(
            method.upper(), url, headers=headers, json=json, timeout=timeout, stream=True
        )
        status = resp.status_code
        resp.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    written += len(chunk)
        return written
    except requests.exceptions.HTTPError as exc:
        body = resp.text[:200] if resp is not None else ""
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
                "request": json,
                "http_status": status,
                "error": error,
                "bytes": written,
                "out_path": str(out_path),
                "latency_ms": int((time.time() - started) * 1000),
            }
        )
