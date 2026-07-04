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
