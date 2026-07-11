"""Console event publisher — the default ``events`` provider.

Prints each published event to the terminal so domain events (circuit
breaker transitions, completed provider calls, backlog writes) are visible
during local/interactive runs with no external system required.
"""

from scripts.providers.base import EventPublisher
from scripts.providers.registry import register
from scripts.utils.console import rprint


@register("events", "console")
class ConsolePublisher(EventPublisher):
    def publish(self, event: str, payload: dict) -> None:
        rprint(f"[dim]event:[/dim] [cyan]{event}[/cyan] {payload}")
