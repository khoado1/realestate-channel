"""Shared rich console helpers.

Centralizes the optional-`rich` import so scripts don't each re-declare the
`try/except ImportError` block and the `rprint` / `rpanel` / `rrule` helpers.
When rich is not installed the helpers degrade to plain `print()` and the
re-exported rich classes are `None` — scripts guard their use behind `RICH`.
"""

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.prompt import Prompt
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None
    Panel = Rule = Table = Markdown = Prompt = None
    Progress = SpinnerColumn = TextColumn = TimeElapsedColumn = None


def rprint(msg):
    console.print(msg) if RICH else print(msg)


def rpanel(msg, **kw):
    console.print(Panel(msg, **kw)) if RICH else print(f"\n{'='*60}\n{msg}\n{'='*60}")


def rrule(msg=""):
    console.print(Rule(msg)) if RICH else print(f"\n--- {msg} ---")
