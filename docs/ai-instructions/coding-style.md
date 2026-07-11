# Coding style instructions

## Purpose
Describes the conventions that already exist across `scripts/` — derived from reading the actual
code, not a generic PEP 8 restatement — so new code matches what's here instead of introducing a
second style. No linter/formatter config is checked into this repo (no `pyproject.toml`,
`.flake8`, `ruff.toml`), so these conventions are the only enforcement mechanism until one is
adopted; follow them by hand.

This doc is about *how code reads*. For *where logic lives* (provider/gateway boundaries, config
vs. code), see [software-architecture.md](software-architecture.md).

## Module docstrings and CLI scripts
Every entrypoint script in `scripts/` opens with a structured module docstring, not a one-liner:
name — pipeline stage: short description, an `===` underline, a paragraph, then `Usage:`,
`Flags:` (only if the script takes flags beyond argparse's own `--help`), and `Output:` sections
listing exactly what files/paths get written. Match this shape for any new entrypoint script —
see `scripts/schedule.py` or `scripts/research.py` for the reference shape. Keep the `Flags:`
section's descriptions in sync with the actual `add_argument(..., help=...)` text; don't let them
drift apart.

## Section banners
Files are divided into labeled sections with a comment banner:
`# ── Section Name ───────────────────────────────────────────────────────────`
(padded to a consistent line width). Order sections top-to-bottom as: API/provider calls →
domain logic → input/selection helpers → output/print functions → save functions → `Main`. New
functions go under the existing banner that matches their role; add a new banner only for a
genuinely new category, not to separate two or three closely related functions.

## Naming and types
- `snake_case` for functions and variables, `UPPER_SNAKE_CASE` for module-level constants
  (`POSTING_SCHEDULE`, `RETENTION_FLAG_LOW`, `LOW_CREDIT_THRESHOLD`), `PascalCase` for classes
  (`RuntimeConfig`, `ClaudeProvider`, `ProviderError`, `PipelineError`).
- Type-hint every function signature. Use modern built-in generics and union syntax
  (`list[dict]`, `dict[str, list[dict]]`, `str | None`) — not `typing.List`/`Optional`. Reach for
  `typing` only for things with no built-in spelling (`Literal`, `Callable`).
- `pathlib.Path` for all path handling in scripts — not `os.path`. The exception is
  `scripts/runtime.py` and `scripts/utils/path_utils.py`, which legitimately operate at the
  `os.path`/`os.getenv` level as the shared resolution layer everything else builds on.

## Strings and formatting
- Double quotes for strings, f-strings for interpolation — no `.format()` or `%`-formatting.
- Manual alignment in dict literals and table/column definitions is intentional, not sloppy
  formatting — e.g. `runtime.py`'s `CONTENT_SUBDIRS` dict, or a `save_report`-style dict where
  colons line up vertically. If this repo ever adopts an autoformatter, configure it to leave
  these alone (or accept the reformat deliberately) rather than losing the alignment as
  incidental churn in an unrelated diff.

## Console output
- Human-facing output goes through `scripts/utils/console.py` (`rprint`, `rpanel`, `rrule`, and
  `Table`/`Panel` for structured layouts), not bare `print()`, in any script that already imports
  from `scripts.utils.console`. Bare `print()` is reserved for the earliest bootstrap errors (e.g.
  `BASE_CONTENT_DIR not set`) that must work even before rich-dependent imports are trusted.
- Status glyphs are consistent and meaningful: `✓` (green, success), `✗` (red, failure), `⚠`
  (yellow, warning). Keep using them rather than inventing new markers — a reader across scripts
  shouldn't have to learn a new vocabulary per file.
- Rich-optional output (checking `if RICH:` and falling back to plain `print`) is only needed
  where you're building a rich-specific widget directly — `Table`, `Panel`, `Progress`, `Markdown`
  — none of which have a meaning outside rich and are `None` when `RICH` is `False`.
  `rprint`/`rpanel`/`rrule` already handle the no-rich fallback internally for plain text, so don't
  add a manual `if RICH:` branch around calls to those.

## Errors
- No bare `except:` — always name the exception (`except ProviderError as e:`,
  `except (ValueError, IndexError):`). For process-fatal-vs-not, see
  [cloud-architecture.md](cloud-architecture.md)'s failure-handling rule (library functions raise
  `PipelineError`/`ProviderError`; only the top-level `if __name__ == "__main__":` block exits the
  process).

## JSON parsing from LLM responses
Stripping accidental markdown fences before `json.loads()` is shared via
`scripts/utils/json_extract.py:parse_json_response()` — `research.py` and `script.py` both call
it rather than each re-implementing the fence-strip. It raises on malformed input and lets the
caller pick its own failure UX (return `[]` vs `{}`, `print` vs `rprint`, with or without a raw
response preview), per [python-refactor.md](../python-refactor.md)'s "thin adapter" convention. If
a third call site needs this, import the helper — don't re-derive the fence-stripping logic.

## Comments
Default to none. The section banners and docstrings already carry the structural explanation;
don't add a comment restating what the next line does. Reserve inline comments for a genuinely
non-obvious constraint — e.g. `runtime.py`'s note on why `env_specs` accepts a fallback-name
tuple, or `generate_voice.py`'s note on why `LOW_CREDIT_THRESHOLD` is sized the way it is.
