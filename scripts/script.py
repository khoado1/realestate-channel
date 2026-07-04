#!/usr/bin/env python3
"""
script.py — Pipeline A: Script Generation
==========================================
Generates a long-form YouTube script + matching Short from a topic,
plus YouTube description, tags, and thumbnail concept.

Usage:
    python3 scripts/script.py                        # interactive mode
    python3 scripts/script.py --backlog              # pick from backlog.md
    python3 scripts/script.py --latest               # pick from latest research report
    python3 scripts/script.py --topic "ARM loans"    # single topic mode

Output:
    - Terminal: rich-formatted script preview
    - File: $SCRIPTS_DIR/YYYY-MM-DD-[slug]-script.md
"""

import sys
import json
import argparse
import re
from datetime import datetime
from pathlib import Path

from scripts.providers import ProviderError, get_provider
from scripts.runtime import RuntimeConfig

runtime = RuntimeConfig(
    paths=["SCRIPTS_DIR", "IDEAS_DIR"],
    env=["CHANNEL_NAME"],
)

BACKLOG_PATH = Path(runtime.IDEAS_DIR) / "backlog.md"

from scripts.utils.console import RICH, Markdown, Prompt, console, rpanel, rprint, rrule


# ── Anthropic API ─────────────────────────────────────────────────────────────
def call_claude(prompt: str, system: str, max_tokens: int = 1000) -> str:
    """Call the configured AI provider and return its text response."""
    try:
        return get_provider("ai").complete(prompt, system=system, max_tokens=max_tokens, timeout=120)
    except ProviderError as e:
        print(f"✗ Claude API error: {e}")
        sys.exit(1)


def build_system_prompt() -> str:
    return f"""You are the head writer for {runtime.CHANNEL_NAME}, a YouTube channel about real estate,
mortgages, and loans. You write in a conversational, relatable tone — like a knowledgeable
friend explaining things over coffee.

Audience: Intermediate. They've researched buying or investing but haven't pulled the trigger.
Skip basics (what a mortgage is). Don't skip nuance (how points affect break-even, real DTI impact).

Writing rules:
- Short sentences. One idea per sentence where possible.
- Second person ("you") not third ("investors")
- Analogies over abstractions — make it concrete
- Occasional rhetorical questions to maintain engagement
- Never start with "Hey guys, welcome back"
- Never use: "game-changer", "deep dive", "unpack", "Furthermore", "Moreover", "In conclusion"
- Hook must land in the first 15 seconds
- Every script ends with exactly one CTA

Always include this disclaimer variant somewhere natural in the script:
"This isn't financial advice — always talk to a licensed professional before making any decisions."

Flag any stat, rate, or price with [verify before filming] inline."""


# ── Script generation ─────────────────────────────────────────────────────────
def generate_longform(topic: str, angle: str = "") -> str:
    """Generate a 6-10 minute long-form script."""
    angle_note = f"\nSpecific angle to take: {angle}" if angle else ""

    prompt = f"""Write a complete YouTube script for this topic: "{topic}"{angle_note}

Format the script with these exact section markers:
[HOOK] — first 15 seconds, must grab attention immediately
[INTRO] — 30-45 seconds, set up what they'll learn and why it matters to them
[SECTION_1: title] — first main point
[SECTION_2: title] — second main point
[SECTION_3: title] — third main point (add more sections if needed)
[RECAP] — 30 seconds, tie it together
[CTA] — one clear call to action, 15-20 seconds

Inline cues to include where relevant:
[B-ROLL SUGGESTION: describe the visual]
[GRAPHIC: describe what to show — numbers, comparisons, process diagrams]
[verify before filming] — next to any rate, price, or time-sensitive stat

Target spoken length: 6-10 minutes (roughly 900-1500 words at natural speaking pace).

Write the full script now — not an outline, the actual word-for-word script."""

    return call_claude(prompt, build_system_prompt(), max_tokens=1000)


def generate_short(topic: str, longform_script: str) -> str:
    """Generate a 45-60 second Short from the long-form script."""
    prompt = f"""Based on this long-form script about "{topic}", create a YouTube Short script.

LONG-FORM SCRIPT:
{longform_script[:3000]}

Rules for the Short:
- 45-60 seconds spoken (roughly 120-150 words)
- Hook in the FIRST LINE — start with the most surprising or counterintuitive moment
- Do NOT summarize the long-form — find the single most compelling insight and build around it
- End with a pattern interrupt CTA: "If you want the full breakdown, it's on the channel"
- No intro, no "welcome back", straight into the content

Format:
[HOOK]
[BODY]
[CTA]

Write the Short script now."""

    return call_claude(prompt, build_system_prompt(), max_tokens=1000)


def generate_metadata(topic: str, longform_script: str) -> dict:
    """Generate YouTube description, tags, and thumbnail concept."""
    prompt = f"""Based on this YouTube script about "{topic}", generate metadata.

SCRIPT EXCERPT (first 500 chars):
{longform_script[:500]}

Return ONLY a JSON object, no preamble, no markdown fences:
{{
  "youtube_title": "compelling SEO-optimized title under 60 characters",
  "youtube_description": "150-word description. First 2 sentences must stand alone as a hook since they show before 'show more'. Include a disclaimer that this is not financial advice. Natural, not keyword-stuffed.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10", "tag11", "tag12", "tag13", "tag14", "tag15"],
  "thumbnail_concept": {{
    "text_overlay": "3-5 words max that create curiosity or tension",
    "visual": "describe the background image or scene in one sentence",
    "color_scheme": "describe the dominant colors and why they work for this topic",
    "emotion": "the feeling the thumbnail should trigger in the viewer"
  }},
  "chapters": [
    {{"time": "0:00", "label": "chapter title"}},
    {{"time": "0:45", "label": "chapter title"}}
  ]
}}"""

    raw = call_claude(prompt, build_system_prompt(), max_tokens=1000)

    try:
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(clean)
    except Exception as e:
        rprint(f"[yellow]⚠ Could not parse metadata JSON: {e}[/yellow]")
        return {}


# ── Input modes ───────────────────────────────────────────────────────────────
def pick_from_backlog() -> tuple[str, str]:
    """Let user pick a topic from backlog.md. Returns (topic, angle)."""
    if not BACKLOG_PATH.exists():
        rprint("[red]✗ backlog.md not found. Run research first: make research[/red]")
        sys.exit(1)

    # Parse unchecked items from backlog
    items = []
    for line in BACKLOG_PATH.read_text().splitlines():
        match = re.match(r"^- \[ \] (.+)$", line.strip())
        if match:
            items.append(match.group(1).strip())

    if not items:
        rprint("[yellow]⚠ No unchecked items in backlog.md. Add ideas or run research first.[/yellow]")
        sys.exit(1)

    rpanel(f"[bold]Backlog — {len(items)} ideas[/bold]", style="cyan")
    for i, item in enumerate(items, 1):
        rprint(f"  [cyan]{i}.[/cyan] {item}")

    rprint("")
    try:
        choice = int(input(f"Pick a number (1-{len(items)}): ").strip())
        topic = items[choice - 1]
    except (ValueError, IndexError):
        rprint("[red]✗ Invalid selection.[/red]")
        sys.exit(1)

    angle = input("Any specific angle or hook to pursue? (press Enter to skip): ").strip()
    return topic, angle


def pick_from_latest_research() -> tuple[str, str]:
    """Pick a topic from the most recent research report. Returns (topic, angle)."""
    scripts_path = Path(runtime.SCRIPTS_DIR)
    reports = sorted(scripts_path.glob("*-research-*.md"), reverse=True)

    if not reports:
        rprint("[red]✗ No research reports found. Run: make research[/red]")
        sys.exit(1)

    latest = reports[0]
    rprint(f"[dim]Loading latest research: {latest.name}[/dim]\n")

    # Parse titles from the report
    ideas = []
    for line in latest.read_text().splitlines():
        match = re.match(r"^### #\d+ (.+)$", line.strip())
        if match:
            ideas.append(match.group(1).strip())

    if not ideas:
        rprint("[red]✗ Could not parse ideas from research report.[/red]")
        sys.exit(1)

    rpanel(f"[bold]Latest Research — {latest.name}[/bold]", style="cyan")
    for i, idea in enumerate(ideas, 1):
        rprint(f"  [cyan]{i}.[/cyan] {idea}")

    rprint("")
    try:
        choice = int(input(f"Pick a number (1-{len(ideas)}): ").strip())
        topic = ideas[choice - 1]
    except (ValueError, IndexError):
        rprint("[red]✗ Invalid selection.[/red]")
        sys.exit(1)

    angle = input("Any specific angle or hook? (press Enter to skip): ").strip()
    return topic, angle


def enter_manually() -> tuple[str, str]:
    """Prompt user to enter a topic manually. Returns (topic, angle)."""
    topic = input("Enter your video topic: ").strip()
    if not topic:
        rprint("[red]✗ Topic cannot be empty.[/red]")
        sys.exit(1)
    angle = input("Any specific angle or hook? (press Enter to skip): ").strip()
    return topic, angle


# ── Output ────────────────────────────────────────────────────────────────────
def print_script_preview(topic: str, longform: str, short: str, metadata: dict):
    """Print a readable preview to terminal."""
    rrule("LONG-FORM SCRIPT")
    if RICH:
        console.print(Markdown(longform[:2000] + ("\n\n_[truncated — see saved file for full script]_" if len(longform) > 2000 else "")))
    else:
        print(longform[:2000])
        if len(longform) > 2000:
            print("\n[truncated — see saved file for full script]")

    rrule("SHORT SCRIPT")
    rprint(short)

    if metadata:
        rrule("METADATA")
        rprint(f"[bold]Title:[/bold] {metadata.get('youtube_title','')}")
        rprint(f"\n[bold]Description:[/bold]\n{metadata.get('youtube_description','')}")
        rprint(f"\n[bold]Tags:[/bold] {', '.join(metadata.get('tags',[]))}")

        thumb = metadata.get("thumbnail_concept", {})
        if thumb:
            rprint(f"\n[bold]Thumbnail:[/bold]")
            rprint(f"  Text overlay: {thumb.get('text_overlay','')}")
            rprint(f"  Visual:       {thumb.get('visual','')}")
            rprint(f"  Colors:       {thumb.get('color_scheme','')}")
            rprint(f"  Emotion:      {thumb.get('emotion','')}")


def save_script(topic: str, longform: str, short: str, metadata: dict) -> str:
    """Save full output to a markdown file in SCRIPTS_DIR."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower())[:40].strip("-")
    filename = f"{date_str}-{slug}-script.md"
    out_path = Path(runtime.SCRIPTS_DIR) / filename

    thumb = metadata.get("thumbnail_concept", {})
    chapters = metadata.get("chapters", [])
    chapters_md = "\n".join(f"- {c.get('time','')} {c.get('label','')}" for c in chapters)

    content = f"""# {metadata.get('youtube_title', topic)}

**Topic:** {topic}
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Status:** draft

---

## YouTube metadata

**Title:** {metadata.get('youtube_title', '')}

**Description:**
{metadata.get('youtube_description', '')}

**Tags:** {', '.join(metadata.get('tags', []))}

**Chapters:**
{chapters_md}

---

## Thumbnail concept

- **Text overlay:** {thumb.get('text_overlay', '')}
- **Visual:** {thumb.get('visual', '')}
- **Color scheme:** {thumb.get('color_scheme', '')}
- **Emotion:** {thumb.get('emotion', '')}

---

## Long-form script (6-10 min)

{longform}

---

## Short script (45-60 sec)

{short}

---

## Production checklist

- [ ] Verify all rates and stats marked [verify before filming]
- [ ] Record long-form
- [ ] Record Short
- [ ] Edit long-form
- [ ] Edit Short
- [ ] Upload with metadata above
- [ ] Schedule via Postiz
- [ ] Run repurpose.py on final video URL
"""

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        return str(out_path)
    except Exception as e:
        rprint(f"[red]✗ Could not save file: {e}[/red]")
        return ""


def mark_backlog_done(topic: str):
    """Mark the topic as done in backlog.md."""
    if not BACKLOG_PATH.exists():
        return
    text = BACKLOG_PATH.read_text()
    updated = text.replace(f"- [ ] {topic}", f"- [x] {topic}")
    BACKLOG_PATH.write_text(updated)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generate a YouTube script + Short + metadata for a real estate topic."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--backlog", action="store_true", help="Pick topic from ideas/backlog.md")
    group.add_argument("--latest",  action="store_true", help="Pick topic from latest research report")
    group.add_argument("--topic",   type=str,            help="Enter topic directly")
    parser.add_argument("--no-save", action="store_true", help="Terminal output only, no file saved")
    args = parser.parse_args()

    # ── Validate environment ──
    if not runtime.CONTENT_DIR:
        print("✗ BASE_CONTENT_DIR not set. Check your .env file.")
        sys.exit(1)

    # ── Header ──
    rpanel(
        f"[bold green]Script Generator[/bold green]\n[dim]Long-form + Short + Metadata[/dim]",
        width=50
    )

    # ── Get topic ──
    if args.topic:
        topic, angle = args.topic, ""
    elif args.backlog:
        topic, angle = pick_from_backlog()
    elif args.latest:
        topic, angle = pick_from_latest_research()
    else:
        # Interactive — offer all three modes
        rprint("\nHow do you want to pick your topic?")
        rprint("  [cyan]1.[/cyan] Pick from backlog")
        rprint("  [cyan]2.[/cyan] Pick from latest research report")
        rprint("  [cyan]3.[/cyan] Enter manually")
        rprint("")
        choice = input("Choice (1/2/3): ").strip()
        if choice == "1":
            topic, angle = pick_from_backlog()
        elif choice == "2":
            topic, angle = pick_from_latest_research()
        else:
            topic, angle = enter_manually()

    rprint(f"\n[bold]Topic:[/bold] {topic}")
    if angle:
        rprint(f"[bold]Angle:[/bold] {angle}")
    rprint("")

    # ── Generate ──
    rprint("[dim]Generating long-form script...[/dim]")
    longform = generate_longform(topic, angle)

    rprint("[dim]Generating Short script...[/dim]")
    short = generate_short(topic, longform)

    rprint("[dim]Generating metadata...[/dim]\n")
    metadata = generate_metadata(topic, longform)

    # ── Output ──
    print_script_preview(topic, longform, short, metadata)

    # ── Save ──
    if not args.no_save:
        saved_path = save_script(topic, longform, short, metadata)
        if saved_path:
            rprint(f"\n[green]✓ Saved:[/green] {saved_path}")

        # Mark done in backlog if it came from there
        if args.backlog:
            mark_backlog_done(topic)
            rprint(f"[green]✓ Marked complete in backlog.md[/green]")


if __name__ == "__main__":
    main()
