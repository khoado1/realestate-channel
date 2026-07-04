# Python refactor guidance

Use these steps when refactoring a Python script so it can be reused in a composable way.

## Goals
- Make the script logic importable and reusable.
- Keep the script file thin and focused on orchestration.
- Preserve existing behavior when run through automation such as Make.

## Refactor pattern
1. Identify the script's core behavior and separate reusable logic from entrypoint logic.
2. Move shared helpers into a utility module such as scripts/utils/path_utils.py.
3. Keep the script file as a thin entrypoint that calls the reusable functions.
4. Prefer a descriptive callable name such as run() over main() when reuse is expected.
5. Use package-style imports such as:
   - from scripts.utils.path_utils import create_directories, resolve
6. Replace duplicated inline helpers (for example, path expansion or environment parsing) with shared utilities whenever the same pattern appears in multiple scripts.
7. When multiple scripts share the same setup flow, extract that bootstrap into a dedicated module such as scripts/runtime.py rather than repeating the same import/load/resolve sequence in each file.
8. Prefer small shared modules that centralize cross-cutting concerns like environment initialization, path resolution, and configuration loading.
9. Make the project importable as a package by adding __init__.py where needed.
10. Run the script as a module when possible:
   - python -m scripts.make_dirs
11. Avoid modifying sys.path manually.
12. Keep function signatures clear and typed.
13. Verify the refactor end to end through the intended workflow, including Make targets.

## Preferred structure
- scripts/make_dirs.py: thin entrypoint
- scripts/utils/path_utils.py: shared helpers
- scripts/__init__.py: package marker

## Notes
- Prefer small, composable functions over one large script-only function.
- Preserve existing CLI behavior, output, and error handling.
- When a helper appears in more than one script, prefer extracting it once and importing it rather than reimplementing it in each file.
- Path handling is a common example: use a shared resolver for environment-variable and home-directory expansion instead of repeating inline logic.
- Repeated environment bootstrap patterns, such as loading dotenv and resolving path values from os.getenv(), should be centralized in a shared module rather than duplicated across scripts.
- For this kind of runtime configuration, prefer a small class that encapsulates the initialization logic and exposes the resolved values as attributes rather than a loose dict or repeated inline setup block.
- Keep environment-resolution logic inside the configuration class instead of patching it per script. When a value needs special handling — such as a fallback to an alternate/legacy variable name (`runtime.X or os.getenv("LEGACY_X")`) — extend the class's spec format to express it declaratively rather than post-processing the resolved attribute in each entrypoint. For example, allow an `env_specs` entry to accept a tuple of fallback names (`(("PRIMARY", "LEGACY"), default)`) that resolves to the first one set, so the script line collapses to a plain `X = runtime.X`.
- When extending the config class's spec format, keep the simple case working unchanged (a plain string name should behave exactly as before) and verify the new behavior end to end: primary set, fallback used, neither set (default), and the plain-name case.
- Once a config object like `runtime` exposes the resolved values as attributes, reference it directly (`runtime.CONTENT_DIR`) throughout the module. Do not copy its attributes into a block of bare module-level constants (`CONTENT_DIR = runtime.CONTENT_DIR`, `IDEAS_DIR = runtime.IDEAS_DIR`, ...). That re-export block is redundant indirection, it gets duplicated across every script, and it hides where the value actually comes from. Delete the block and update the usages to go through the config object.
- In a config spec, separate the *default* (a project fact) from the *selection* (which values a given script needs). The selection is legitimately per-script and worth keeping local — it documents each script's dependencies. The defaults are not: a default like `os.path.join(content_dir, "ideas")` or `"realestate-channel"` is identical everywhere it appears, so inlining it in each script's spec duplicates it and lets it drift (e.g. one script defaulting a directory to `content_dir/scripts` while another defaults the same name to `""`). Keep the defaults in one shared catalog (a name→subdir map, a name→default map) that the config class consults, and let scripts declare only the names they need (`paths=["IDEAS_DIR"]`, `env=["CHANNEL_NAME"]`). Fixing such drift is a behavior change, so verify each affected value end to end.
- When centralizing defaults into a catalog, keep an escape hatch for one-off values the catalog does not know about (e.g. an explicit `path_specs=[(name, spec)]`) so the catalog stays additive rather than a hard constraint, and raise a clear error when a script names an unknown key.

## External integrations (providers)
- Give each capability the code consumes (AI text, audio, video, …) one abstract interface, and make concrete API integrations implement it and self-register with a registry. Scripts ask for a *kind* (`get_provider("ai")`) and get whichever implementation is selected at runtime by a `<KIND>_PROVIDER` env var with a sensible default — this is a plugin model: adding a provider is drop-in, no caller changes.
- When the same integration is called from several scripts (four copies of `call_claude` here), the duplicated request/auth/parse boilerplate belongs in the provider. Keep a *thin* per-script adapter only where the scripts genuinely differ — e.g. one wants a fatal exit on error, another wants a graceful placeholder. Providers should `raise` a typed error and stay silent (no `print`/`sys.exit`); the script owns the UX.
- Funnel every provider HTTP call through one shared boundary module. It gives uniform error mapping, one place for timeouts/streaming, and a single seam to record calls. Providers read their own credentials from the environment (not from a script's config object) so they stay decoupled from any one entrypoint.

## Cross-cutting persistence / observability
- Concerns like logging every API call (inputs/outputs/errors/cost) belong at the shared boundary, wired in via a recorder seam — not sprinkled into each provider or script. Providers annotate calls with lightweight context (provider/kind/operation/model) via a context manager; the boundary merges that with the transport details and hands it to whatever recorder is installed. The recorder is a no-op until a store installs one, so the boundary has no dependency on the store.
- Keep the store and the boundary decoupled in both directions: the store imports the boundary (to install its recorder), so the boundary must never import the store. If a package auto-enables the store on import, use a lazy import inside the enable function so either import order works — a top-level cross-import will silently half-initialize one module and the wiring will vanish. Verify both import orders.
- Persist large inputs/outputs (audio, video, big streams) to the filesystem and store only a path + checksum + size in the row. Redact secrets before persisting; prefer designs where secrets never reach the recorder at all (keep auth in headers, which aren't recorded). Store enough to *reconstruct and replay* a call.
- When a cost/quota can't be known exactly, record an estimate and flag it (`estimated`) rather than omitting it or blocking — and keep the rate table as data you can correct, not literals.

## Config, not code
- Tunables (model ids, voice/render settings), rule sets (e.g. regex cleanup passes), and pricing tables are data, not logic. Put them in declarative files (TOML via stdlib `tomllib` needs no dependency) loaded through one small cached loader, and have code read the loaded values. This lets non-code changes (a new model, a tweaked voice setting, an added cleanup rule) happen without touching Python, and co-locates a provider's settings with the provider.
- A regex-cleanup pipeline is a good example: express each pass as `{pattern, replacement, flags}` in a data file and apply them in order with a shared `apply_rules` helper, instead of a long hardcoded sequence of `re.sub` calls. When moving logic to data, verify the data-driven output is byte-identical to the original on a representative sample.
- Not everything embedded is config: argument help text documents the flag it sits next to and reads best inline with the `argparse` definition — moving it into a config file adds indirection without real reuse. Extract genuinely shared *flag definitions* into a helper if several scripts share them; leave per-command help where it is.
