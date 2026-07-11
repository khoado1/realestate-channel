# Security instructions

## Purpose
Baseline security rules for a codebase expanding from a single-operator tool into a multi-tenant
SaaS product. Multi-tenancy, auth, and secrets-storage are already decided in
[platform-architecture.md](../platform-architecture.md) — WorkOS for auth, encrypted Postgres
columns for credentials (not Vault), hybrid RLS + dedicated-DB-per-tenant isolation. Don't invent
alternatives to those decisions; the rules below are what holds regardless of exactly when that
migration lands.

## Secrets
- Never log, print, or record a secret, in full or in part. `scripts/env_check.py` prints
  `value[:6]` of every API key to stdout as a "looks configured" check — a truncated prefix still
  meaningfully narrows guessing space and shows up in terminal scrollback, CI logs, and screen
  shares. Confirm presence with a boolean (`"set" if value else "MISSING"`), never a slice of the
  value.
- Secrets stay in request headers and environment variables, never in a request/response body that
  could reach the call-recording store. This is already the design intent per
  [python-refactor.md](../python-refactor.md)'s recorder seam ("prefer designs where secrets never
  reach the recorder at all"); keep new code consistent with it.
- Don't duplicate credential-resolution logic outside `scripts/providers/`. `scripts/store/calls.py`'s
  replay path rebuilds its own `{provider: env_var}` auth map instead of asking the provider for its
  credential — every extra place that knows how to fetch a given provider's secret is one more place
  that can leak it or drift out of sync with a rotation.
- Don't let one provider's credential silently stand in for another's. `scripts/providers/hyperframes.py`
  falls back to `ELEVENLABS_API_KEY` when `HYPERFRAMES_API_KEY` is unset. If cross-provider
  credential sharing is ever genuinely intended, make it an explicit, named config choice — never an
  implicit `getenv(A) or getenv(B)` fallback that masks a missing credential as a working one.
- Today's flat global `<PROVIDER>_API_KEY` env vars are an accepted stopgap for the current
  single-operator scope, not a pattern to extend. New code should read credentials through the
  provider's existing lookup function rather than adding new direct `os.getenv` calls, so swapping
  that function's internals for an `Integration`-backed resolver (platform-architecture.md §3) later
  is a one-place change.

## Tenant isolation
- Every tenant-scoped table in the decided data model carries `org_id` for RLS enforcement
  (platform-architecture.md §3, table sketch). When adding any new persistent table or object-storage
  key, follow that pattern — an `org_id` column from the start, not bolted on once real tenants exist.
  A single-tenant assumption baked into a schema is far more expensive to unwind later than to avoid
  now.
- `scripts/store/db.py`'s call-recording SQLite schema has no `org_id`, which is fine — it's
  diagnostic/observability data outside the decided multi-tenant system of record (Postgres), not a
  gap to retroactively patch on its own. If this store's data ever needs tenant scoping, it follows
  the same `org_id`-column convention already established for every other table, not a bespoke
  solution invented locally.

## Trust boundaries
- Validate and sanitize anything crossing from outside the process — webhook payloads, user-submitted
  content, uploaded files — at the boundary where it enters, not deep inside business logic. Once
  `scripts/` code runs as a Temporal activity invoked by the Java orchestrator, that includes
  payloads arriving from the orchestrator: don't assume input is already safe just because it came
  from "internal" infrastructure rather than a public endpoint.
- Prefer parameterized queries and typed request/response models over string concatenation or raw
  dict passthrough wherever a user- or tenant-supplied value reaches a database query, shell
  command, or file path.
