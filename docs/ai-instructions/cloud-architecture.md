# Cloud and infrastructure architecture instructions

## Purpose
Rules for keeping `scripts/` compatible with the target architecture already decided in
[platform-architecture.md](../platform-architecture.md): this Python code is being promoted into
Temporal-activity-backed workers behind a Java/Spring Boot orchestrator, Postgres, and MinIO — not
rewritten from scratch. The current work is *hardening scripts/ ahead of that migration*, per
`memory/cloud-native-hardening-plan.md` (session notes, not auto-loaded — read it for the current
open-todo state before starting new cloud-native hardening work).

Treat every rule below as "would this survive being invoked as a Temporal activity, concurrently,
across multiple workers, for multiple orgs" — not "does this work when I run it locally."

## No import-time global state
- Configuration, credentials, and anything that varies by tenant or request must not be resolved
  once at import time into a module-level singleton. `scripts/runtime.py`'s `RuntimeConfig`,
  instantiated as `runtime = RuntimeConfig(...)` at the top of seven scripts, bakes in one
  `.env`/`BASE_CONTENT_DIR`/channel identity for the life of the process. A Temporal activity
  receives its org/project context as an explicit argument (the `StepRun`'s `org_id`/`project_id`
  per platform-architecture.md §3) — new code should resolve config from an argument passed in at
  call time, not a module attribute, so it's already shaped like an activity function instead of
  needing a rewrite when it's wrapped into one.
- Per-process resilience state (the gateway's circuit breaker, `scripts/gateway/circuit_breaker.py`)
  is fine to keep in-memory — that's standard practice, and each worker replica having its own
  circuit-breaker view of a host is expected, not a bug. The distinction that matters: state that
  describes *this process's* view of the world (circuit breaker) can stay local; state that's the
  system of record for a tenant's data (credentials, call history that matters beyond diagnostics)
  must not — see Postgres/MinIO note below.

## Local disk and the local store
- Postgres + MinIO are the decided system of record (platform-architecture.md §1, §5); don't grow a
  second one. `scripts/store/repository.py`'s SQLite file is a deliberate, scoped-down choice for
  call-recording/diagnostics (`memory/cloud-native-hardening-plan.md` — "did *not* build a separate
  API/service layer for this... premature until there's an actual second process consuming it") —
  it's fine to leave as-is for its current purpose. Don't extend it to hold data that needs to be
  visible across workers or survive a tenant's actual business data lifecycle (assets, workflow
  state, published posts) — that belongs in Postgres/MinIO per the decided data model, not a new
  local file.

## Idempotency and resumability
- Temporal's `RetryOptions` gives workflow/activity-level retry for free (platform-architecture.md
  §6) — don't hand-roll retry logic at that layer. What Temporal does *not* give for free: any
  side effect an activity performs outside Temporal's own state gets duplicated if the activity is
  retried from scratch, since Temporal has no idea the side effect already happened once.
  `scripts/research.py`'s `append_to_backlog` and `scripts/analytics.py`'s
  `append_feedback_to_backlog` both do unconditional `open(path, "a")` — a retry duplicates entries.
  This is the open todo tracked in `memory/cloud-native-hardening-plan.md` (#1): a
  content-hash-keyed `append_once(path, key, content)` helper, not a random UUID (a UUID solves the
  gateway's HTTP-retry-dedup problem, which is a *different* idempotency problem — see
  [python-refactor.md](../python-refactor.md)'s note distinguishing the two).
- Any operation that can outlive a single process invocation must persist its progress rather than
  hold it only in a local loop variable. `scripts/generate_video.py`'s `poll_and_download` blocks
  synchronously in a `while` loop until the render finishes; a worker restart mid-poll silently
  abandons the job with no record it was ever started. Long-running polling belongs on Temporal's
  own durable-timer/signal mechanism once this is an activity, not a local `time.sleep` loop —
  don't add more code that assumes the process stays alive for the full duration of a slow external
  job.

## Failure handling
- Library-style functions must never be process-fatal. A `sys.exit(1)` inside a function called
  from `scripts/schedule.py` or `scripts/providers/calls.py`'s `on_error="exit"` path kills the
  whole process — and once this code runs as a Temporal worker, that kills every other in-flight
  activity on that worker, not just the failing one. Reserve `sys.exit`/process-fatal handling for
  the top-level CLI entrypoint only; everything underneath raises a typed error so the caller (or,
  later, Temporal's retry policy — which already distinguishes retryable from non-retryable errors
  like bad credentials, per platform-architecture.md §6) can decide what happens next.

## Credentials
- The decided target is `Integration` rows (encrypted Postgres columns, org/project-scoped) per
  platform-architecture.md §1/§3 — not Vault, not a bespoke per-script secrets system. Don't build
  an alternative multi-tenant credential mechanism in `scripts/`. Do keep credential lookup behind
  the seam that already exists (one function per provider in `scripts/providers/`) rather than
  spreading `os.getenv("...API_KEY")` calls further, so that seam is where a future
  Integration-backed resolver plugs in — see [security.md](security.md) for the specific rules.
