#!/usr/bin/env python3
"""
research.py — Pipeline A: Research & Ideation
==============================================
Researches trending real estate & loan topics across multiple sources
and generates ranked video ideas.

Usage:
    python3 scripts/research.py                    # interactive mode
    python3 scripts/research.py --auto             # watchlist mode
    python3 scripts/research.py --topic "ARM loans" # single topic mode

Output:
    - Terminal: rich-formatted ranked idea table
    - File: $SCRIPTS_DIR/YYYY-MM-DD-research.md
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

from scripts.runtime import RuntimeConfig

runtime = RuntimeConfig(
    path_specs=[
        ("SCRIPTS_DIR", lambda content_dir: os.path.join(content_dir, "scripts")),
        ("IDEAS_DIR", lambda content_dir: os.path.join(content_dir, "ideas")),
    ],
    env_specs=[("CHANNEL_NAME", "realestate-channel")],
)

# Watchlist file — add topics here for --auto mode
WATCHLIST_PATH = Path(runtime.IDEAS_DIR) / "watchlist.md"

# ── Try importing rich for pretty output ─────────────────────────────────────
try:
    from rich.console import Console
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich import print as rprint
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None
    print("⚠ rich not installed — run: pip3 install rich")
    print("  Falling back to plain text output.\n")

# ── Sources config ────────────────────────────────────────────────────────────
REDDIT_SUBS = [
    "FirstTimeHomeBuyer",
    "RealEstate",
    "personalfinance",
    "Mortgages",
    "realestateinvesting",
]

NEWS_SITES = [
    "housingwire.com",
    "inman.com",
    "themortgagereports.com",
    "calculatedriskblog.com",
]

# Default topics for watchlist mode if watchlist.md doesn't exist yet
DEFAULT_WATCHLIST = [
    "mortgage rates",
    "FHA loans",
    "first time home buyer",
    "real estate market 2025",
    "home equity loan vs HELOC",
    "adjustable rate mortgage",
    "down payment assistance",
    "real estate investing",
]

# ── Anthropic API call ────────────────────────────────────────────────────────
def call_claude(prompt: str, system: str = "") -> str:
    """Call Claude API and return text response."""
    import requests

    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "system": system or build_system_prompt(),
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        texts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(texts)
    except requests.exceptions.RequestException as e:
        print(f"✗ Claude API error: {e}")
        sys.exit(1)


def build_system_prompt() -> str:
    return f"""You are the research assistant for {runtime.CHANNEL_NAME}, a YouTube channel about
real estate, mortgages, and loans. Your audience is intermediate — they've done research
but haven't done a deal yet. Tone is conversational and relatable, like a knowledgeable friend.

When generating video ideas, always output valid JSON only — no preamble, no markdown fences.
Format exactly as shown in the user prompt."""


# ── Research functions ────────────────────────────────────────────────────────
def research_topic(topic: str) -> list[dict]:
    """
    Research a topic and return ranked video ideas.
    Returns a list of idea dicts.
    """
    prompt = f"""Research this real estate/loan topic for YouTube content: "{topic}"

Consider these sources and angles:
- What questions are people asking on Reddit (r/RealEstate, r/FirstTimeHomeBuyer, r/Mortgages)?
- What YouTube videos on this topic have high views on small channels (strong search demand)?
- What's trending or timely about this topic right now?
- What news sites like HousingWire and Inman are covering?

Generate exactly 5 ranked video ideas. Output ONLY a JSON array, no other text:

[
  {{
    "rank": 1,
    "title": "compelling YouTube title here",
    "type": "explainer|news|case_study",
    "angle": "one sentence — the specific hook or counterintuitive take",
    "why_now": "one sentence — why this is timely or searchable right now",
    "search_demand": "high|medium|low",
    "difficulty": "easy|medium|hard",
    "time_sensitive_data": true
  }}
]

time_sensitive_data = true if the script will need rates, prices, or stats that need verification before filming."""

    raw = call_claude(prompt)

    try:
        import json
        # Strip accidental markdown fences if present
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(clean)
    except Exception as e:
        print(f"✗ Failed to parse Claude response as JSON: {e}")
        print("Raw response:", raw[:500])
        return []


def research_multiple(topics: list[str]) -> dict[str, list[dict]]:
    """Research multiple topics and return results keyed by topic."""
    results = {}
    for i, topic in enumerate(topics, 1):
        if RICH:
            console.print(f"[dim]({i}/{len(topics)}) Researching:[/dim] [bold]{topic}[/bold]")
        else:
            print(f"({i}/{len(topics)}) Researching: {topic}")
        results[topic] = research_topic(topic)
    return results


# ── Output functions ──────────────────────────────────────────────────────────
def print_results_rich(results: dict[str, list[dict]]):
    """Pretty-print results using rich."""
    for topic, ideas in results.items():
        console.print()
        console.print(Panel(f"[bold]{topic.upper()}[/bold]", style="green"))

        if not ideas:
            console.print("[red]No ideas returned for this topic.[/red]")
            continue

        table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
        table.add_column("#",       style="dim", width=3)
        table.add_column("Title",               width=42)
        table.add_column("Type",    style="dim", width=12)
        table.add_column("Demand",  style="dim", width=8)
        table.add_column("⚠ Time?", style="dim", width=8)

        for idea in ideas:
            flag = "[yellow]yes[/yellow]" if idea.get("time_sensitive_data") else "[green]no[/green]"
            demand_color = {"high": "green", "medium": "yellow", "low": "red"}.get(
                idea.get("search_demand", ""), "white"
            )
            table.add_row(
                str(idea.get("rank", "")),
                idea.get("title", ""),
                idea.get("type", ""),
                f"[{demand_color}]{idea.get('search_demand', '')}[/{demand_color}]",
                flag,
            )
            console.print(f"  [dim]↳ {idea.get('angle', '')}[/dim]")
            console.print(f"  [dim]  Why now: {idea.get('why_now', '')}[/dim]")
            console.print()

        console.print(table)
        console.print()


def print_results_plain(results: dict[str, list[dict]]):
    """Plain text fallback output."""
    for topic, ideas in results.items():
        print(f"\n{'='*60}")
        print(f"TOPIC: {topic.upper()}")
        print('='*60)
        for idea in ideas:
            print(f"\n#{idea.get('rank')} [{idea.get('type','').upper()}] {idea.get('title','')}")
            print(f"   Angle:    {idea.get('angle','')}")
            print(f"   Why now:  {idea.get('why_now','')}")
            print(f"   Demand:   {idea.get('search_demand','')}  |  Time-sensitive: {idea.get('time_sensitive_data','')}")


def save_results(results: dict[str, list[dict]], topics: list[str]):
    """Save research results to markdown file in SCRIPTS_DIR."""
    import json

    date_str  = datetime.now().strftime("%Y-%m-%d")
    slug      = topics[0].lower().replace(" ", "-")[:30] if len(topics) == 1 else "multi-topic"
    filename  = f"{date_str}-research-{slug}.md"
    out_path  = Path(runtime.SCRIPTS_DIR) / filename

    # Build markdown
    lines = [
        f"# Research Report — {date_str}",
        f"**Topics:** {', '.join(topics)}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
    ]

    for topic, ideas in results.items():
        lines.append(f"## {topic.title()}")
        lines.append("")
        for idea in ideas:
            flag = "⚠ verify rates before filming" if idea.get("time_sensitive_data") else ""
            lines.append(f"### #{idea.get('rank')} {idea.get('title','')}")
            lines.append(f"- **Type:** {idea.get('type','')}")
            lines.append(f"- **Search demand:** {idea.get('search_demand','')}")
            lines.append(f"- **Difficulty:** {idea.get('difficulty','')}")
            lines.append(f"- **Angle:** {idea.get('angle','')}")
            lines.append(f"- **Why now:** {idea.get('why_now','')}")
            if flag:
                lines.append(f"- **{flag}**")
            lines.append("")

    lines += [
        "---",
        "",
        "## Add to backlog",
        "",
        "<!-- Copy titles you want to pursue into ideas/backlog.md -->",
        "",
        "```",
        json.dumps(results, indent=2),
        "```",
    ]

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return str(out_path)
    except Exception as e:
        print(f"✗ Could not save file: {e}")
        return None


def append_to_backlog(results: dict[str, list[dict]]):
    """Append top ideas to the ideas backlog."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [f"\n## {date_str} research batch\n"]

    for topic, ideas in results.items():
        lines.append(f"**{topic}**")
        for idea in ideas[:3]:  # top 3 per topic
            lines.append(f"- [ ] {idea.get('title','')}")
        lines.append("")

    try:
        backlog = Path(runtime.IDEAS_DIR) / "backlog.md"
        backlog.parent.mkdir(parents=True, exist_ok=True)
        with open(backlog, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        print(f"⚠ Could not update backlog: {e}")


def load_watchlist() -> list[str]:
    """Load topics from watchlist.md, falling back to defaults."""
    if WATCHLIST_PATH.exists():
        topics = []
        for line in WATCHLIST_PATH.read_text().splitlines():
            line = line.strip().lstrip("-").lstrip("*").strip()
            if line and not line.startswith("#"):
                topics.append(line)
        return topics if topics else DEFAULT_WATCHLIST
    else:
        # Create default watchlist on first run
        WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        content = "# Research Watchlist\n# One topic per line. Run: make research --auto\n\n"
        content += "\n".join(f"- {t}" for t in DEFAULT_WATCHLIST)
        WATCHLIST_PATH.write_text(content)
        print(f"✓ Created default watchlist at {WATCHLIST_PATH}")
        return DEFAULT_WATCHLIST


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Research trending real estate topics for YouTube content."
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Watchlist mode — read topics from ideas/watchlist.md",
    )
    parser.add_argument(
        "--topic",
        type=str,
        help="Single topic mode — research one specific topic",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip saving to file — terminal output only",
    )
    args = parser.parse_args()

    # ── Validate environment ──
    if not runtime.CONTENT_DIR:
        print("✗ BASE_CONTENT_DIR not set. Check your .env file.")
        sys.exit(1)

    # ── Determine topics ──
    if args.topic:
        topics = [args.topic]
        mode = "single"
    elif args.auto:
        topics = load_watchlist()
        mode = "watchlist"
    else:
        # Interactive mode
        if RICH:
            console.print(Panel(
                "[bold green]Research & Ideation[/bold green]\n"
                "[dim]Real estate YouTube content pipeline[/dim]",
                width=50
            ))
        print()
        raw = input("Enter topic(s) to research (comma-separated, or press Enter for watchlist):\n> ").strip()
        if raw:
            topics = [t.strip() for t in raw.split(",") if t.strip()]
            mode = "interactive"
        else:
            topics = load_watchlist()
            mode = "watchlist"

    if RICH:
        console.print(f"\n[dim]Mode: {mode} | Topics: {len(topics)}[/dim]\n")
    else:
        print(f"\nMode: {mode} | Topics: {len(topics)}\n")

    # ── Run research ──
    results = research_multiple(topics)

    # ── Print results ──
    if RICH:
        print_results_rich(results)
    else:
        print_results_plain(results)

    # ── Save results ──
    if not args.no_save:
        saved_path = save_results(results, topics)
        append_to_backlog(results)
        if saved_path:
            if RICH:
                console.print(f"[green]✓ Saved:[/green] {saved_path}")
                console.print(f"[green]✓ Backlog updated:[/green] {runtime.IDEAS_DIR}/backlog.md")
            else:
                print(f"✓ Saved: {saved_path}")
                print(f"✓ Backlog updated: {runtime.IDEAS_DIR}/backlog.md")


if __name__ == "__main__":
    main()
