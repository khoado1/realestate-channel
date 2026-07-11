# Software architecture instructions

## Purpose
General separation-of-concerns and module-boundary rules for this codebase, independent of any
one refactor. See [python-refactor.md](../python-refactor.md) for the Python-specific implementation
pattern (providers, gateway, config classes) these rules assume already exists.

Today's `scripts/` modules are the direct ancestors of tomorrow's Temporal activities (see
[platform-architecture.md](../platform-architecture.md) §6) — a script that respects these
boundaries now gets lifted into an Activity with minimal change; one that doesn't needs a rewrite,
not a lift.

## Layering and boundaries
- Every script is orchestration only: parse inputs, call domain/provider logic, format output.
  Business logic and I/O belong in `scripts/utils/`, `scripts/providers/`, or `scripts/gateway/` —
  never inline in the entrypoint script.
- Every outbound call to an external service crosses exactly one boundary: `scripts/gateway/send()`
  via a registered provider. A script calling `requests.request()` (or any HTTP client) directly is
  a layering violation, not a shortcut — it silently loses retry/backoff, circuit-breaking, call
  recording, and idempotency-key handling that every other integration gets for free.
  `scripts/schedule.py`'s Postiz calls do this today; treat that as the canonical counter-example,
  and route it through the gateway when next touched.
- Don't reimplement a cross-cutting concern in a second location because the first one is
  inconvenient to reach. `scripts/store/calls.py` re-derives a provider-to-API-key map for replay
  instead of asking `scripts/providers/` for it — this duplicates credential-handling logic outside
  the module that owns it, and the two copies will drift.

## Single responsibility
- A "thin adapter" (a script-local wrapper that only varies a config `name`, `max_tokens`, or
  `on_error` policy) is acceptable per [python-refactor.md](../python-refactor.md). The moment an
  adapter grows a second reason to change — new parsing, a new retry rule, a new data shape —
  promote it into the provider or a shared helper instead of letting each script's copy diverge.
- Config and tunables are data, not code, per the config-not-code rule already established. A
  hardcoded schedule/threshold/rule dict inside a script (e.g. `POSTING_SCHEDULE` in
  `scripts/schedule.py`) is a separation-of-concerns violation as much as a resilience one: it
  couples "what the values are" to "where the script happens to live," so tuning it requires a
  code change instead of an edit to `scripts/config/*.toml`.

## Verifying the boundary is real
- When adding or touching an integration, grep for the pattern first
  (`grep -rn 'requests\.' scripts/ | grep -v gateway`) to confirm nothing else bypasses the gateway
  the same way — these bypasses tend to get copy-pasted the same way the pre-refactor `call_claude`
  duplication was.
- A module reaching past its declared dependency (a script importing another script's internals, a
  store reading raw env vars for something a provider already owns) signals the abstraction is
  incomplete, not that the caller found a valid shortcut. Fix the boundary; don't route around it.
