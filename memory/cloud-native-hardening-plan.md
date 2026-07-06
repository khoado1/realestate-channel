# Cloud-native hardening plan (session notes)

Transitory session notes, not durable project guidance — deliberately **not** wired into
`CLAUDE.md`/`AGENTS.md`, so it won't get auto-loaded into every session's context. Kept here
(rather than only in local `~/.claude` memory) so it survives switching laptops, since Claude
Code's local memory is machine-local and doesn't sync.

## Why this work exists

`docs/platform-architecture.md` (added 2026-07-04, status "whiteboard / pre-implementation") specs converting this repo's single-user Python CLI content pipeline into a multi-tenant SaaS: Java/Spring Boot API + Temporal orchestration + Postgres/MinIO + k8s, with the existing `scripts/` pipeline scripts (`research.py`, `script.py`, `repurpose.py`, `analytics.py`, etc.) promoted into Temporal-activity-backed Python workers. None of that migration is built yet.

This work is proactively hardening the *current* Python scripts against the cloud-native issues that migration will surface (retries, observability, idempotency, statelessness) so there's less rework later — not building the migration itself.

**How to apply:** When resuming this work, don't jump to implementing the Temporal/Java/Postgres side — stay scoped to hardening the existing `scripts/` Python code. Read `docs/python-refactor.md` first; every pattern established so far (gateway, structured logging, provider-calls helper, repository pattern) is documented there in detail — that doc is the living source of "how we build things here," this file is just the roadmap/todo state.

## Already done

- **API gateway** (`scripts/gateway/`): retry w/ exponential backoff + jitter, per-host circuit breaker, both config-driven (`scripts/config/gateway.toml`). All provider HTTP calls route through it via `scripts/providers/http.py`.
- **Idempotency keys on the gateway**: POST/PATCH calls get a UUID `Idempotency-Key` header, generated once per logical call and reused across retries — solves *retried-HTTP-attempt* duplication only (not whole-script-rerun duplication, see open todo below).
- **Structured logging** (`scripts/utils/logging.py`): JSON-lines to stderr, separate from Rich's stdout human output. Wired into gateway retries/circuit-breaker transitions (state changes only, not every call).
- **Shared call helpers** (`scripts/providers/calls.py`): `call_ai(name, prompt, channel_name, on_error=...)` replaced 4 duplicated `call_claude` functions across `analytics.py`/`research.py`/`repurpose.py`/`script.py`; `youtube_get(...)` replaced duplicated YouTube Data API calls.
- **Prompt config** (`scripts/config/prompts.toml` + `scripts/utils/prompts.py`): each script's Claude system prompt composed from shared channel voice + per-script persona/rules, instead of hardcoded f-strings.
- **Repository pattern for the call store** (`scripts/store/repository.py`): `CallRepository` ABC + `SQLiteCallRepository`, decouples `calls.py`/`report.py` from raw SQLite. Deliberately did *not* build a separate API/service layer for this — premature until there's an actual second process consuming it (that's the already-scoped Postgres+Spring-Boot migration in platform-architecture.md).

## Done since last update

1. **Fixed backlog.md double-append idempotency.** Added `scripts/utils/markdown.py::append_once(path, content)` — hashes the content internally (`sha256(content)[:12]`) and writes an `<!-- signal:<hash> -->` marker after the appended block, skipping the write if that marker already exists. Both `research.py::append_to_backlog` and `analytics.py::append_feedback_to_backlog` just call `append_once(backlog, "\n".join(lines))`, replacing the old unconditional `open(..., "a")` writes. Originally had callers compute their own `key = hashlib.sha256(...)` and pass it in alongside `content` — collapsed that into `append_once` itself once it was clear both call sites hashed the content the same way, so neither script needs `hashlib` anymore. Verified end to end (via a scratch `uv venv` with the repo's real deps, since none were installed in this environment): identical rerun on the same data → skipped with a warning printed; changed data → still appends a new block with a new marker.

## Open todos

1. **Add a unit and mock testing layer** — no test suite exists in this repo at all yet. Scope not yet discussed (framework choice, what to prioritize covering first — likely the gateway/repository/provider-calls modules, since they're newly testable in isolation).
2. **Add pub/sub event hooks** — publish events/event args through a generic subscriber provider layer, console as the default provider, pluggable to external systems like Kafka. A different concern from the observability/logging layer, though following the same provider-plugin pattern (registry + env-var-selected implementation, like `get_provider("ai")`).

Neither of these two has been started as of this writing.
