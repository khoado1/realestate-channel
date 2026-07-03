#!/usr/bin/env python3
"""
schedule.py — Pipeline A: Content Scheduling via Postiz
========================================================
Reads repurposed content files and pushes them to Postiz as
drafts (default) or scheduled posts for LinkedIn, X/Twitter,
and YouTube Shorts video queue.

Usage:
    python3 scripts/schedule.py                        # interactive — pick repurposed folder
    python3 scripts/schedule.py --latest               # auto-pick most recent repurposed folder
    python3 scripts/schedule.py --dir <path>           # specify repurposed folder directly
    python3 scripts/schedule.py --latest --schedule    # schedule directly instead of draft

Flags:
    --schedule     Push as scheduled posts (uses optimal posting times)
    --draft        Push as drafts for review in Postiz (default)
    --dry-run      Preview what would be sent without calling Postiz API

Output:
    - Terminal: summary of what was pushed and Postiz post IDs
    - Appends schedule log to $REPURPOSED_DIR/schedule-log.md
"""

import os
import sys
import re
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()

def _r(v): return os.path.expandvars(os.path.expanduser(v)) if v else ""

CONTENT_DIR    = _r(os.getenv("BASE_CONTENT_DIR", ""))
REPURPOSED_DIR = _r(os.getenv("REPURPOSED_DIR", os.path.join(CONTENT_DIR, "repurposed")))
POSTIZ_API_KEY = os.getenv("POSTIZ_API_KEY", "")
CHANNEL_NAME   = os.getenv("CHANNEL_NAME", "realestate-channel")

POSTIZ_BASE_URL = "https://api.postiz.com/public/v1"

# ── Optimal posting schedule (from CLAUDE.md) ────────────────────────────────
# Days: 0=Monday ... 6=Sunday
POSTING_SCHEDULE = {
    "linkedin": {
        "days": [1, 2, 3],          # Tue, Wed, Thu
        "hour": 9,                  # 9am local
        "minute": 0,
    },
    "twitter": {
        "days": [0, 1, 2, 3, 4],   # Mon-Fri
        "hour": 8,
        "minute": 0,
    },
    "youtube_short": {
        "days": [0, 1, 2, 3, 4, 5, 6],  # daily
        "hour": 10,
        "minute": 0,
    },
}

# ── Rich setup ────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.rule import Rule
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None

def rprint(msg):   console.print(msg) if RICH else print(msg)
def rpanel(msg, **kw): console.print(Panel(msg, **kw)) if RICH else print(f"\n{'='*60}\n{msg}\n{'='*60}")
def rrule(msg=""):  console.print(Rule(msg)) if RICH else print(f"\n--- {msg} ---")


# ── Postiz API ────────────────────────────────────────────────────────────────
def postiz_request(method: str, endpoint: str, payload: dict = None) -> dict:
    """Make a request to the Postiz API."""
    import requests

    if not POSTIZ_API_KEY:
        rprint("[red]✗ POSTIZ_API_KEY not set in .env[/red]")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {POSTIZ_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{POSTIZ_BASE_URL}/{endpoint.lstrip('/')}"

    try:
        resp = requests.request(
            method.upper(),
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        rprint(f"[red]✗ Postiz API error {resp.status_code}: {resp.text}[/red]")
        raise
    except requests.exceptions.RequestException as e:
        rprint(f"[red]✗ Postiz connection error: {e}[/red]")
        raise


def get_postiz_channels() -> list[dict]:
    """Fetch connected channels from Postiz."""
    try:
        data = postiz_request("GET", "/channels")
        return data.get("channels", data) if isinstance(data, dict) else data
    except Exception:
        return []


# ── Content parsers ───────────────────────────────────────────────────────────
def parse_linkedin(path: Path) -> str:
    """Extract post body from linkedin.md."""
    text = path.read_text(encoding="utf-8")
    # Strip frontmatter header lines
    lines = text.splitlines()
    body_lines = []
    in_body = False
    for line in lines:
        if line.strip() == "---":
            in_body = not in_body
            continue
        if in_body or (not line.startswith("#") and not line.startswith("_")):
            body_lines.append(line)
    return "\n".join(body_lines).strip()


def parse_twitter_thread(path: Path) -> list[str]:
    """
    Parse twitter.md into a list of individual tweets.
    Expects tweets numbered as: 1/ 2/ 3/ etc.
    """
    text = path.read_text(encoding="utf-8")
    tweets = []

    # Match numbered tweets: 1/ ... 2/ ...
    pattern = r"^\d+/\s*(.+?)(?=^\d+/|\Z)"
    matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL)

    if matches:
        for match in matches:
            tweet = match.strip()
            # Clean up any markdown formatting artifacts
            tweet = re.sub(r"\n+", " ", tweet).strip()
            if tweet:
                tweets.append(tweet)
    else:
        # Fallback: split by blank lines
        blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
        tweets = [b for b in blocks if not b.startswith("#") and not b.startswith("_")]

    return tweets


def parse_short_script(path: Path) -> str:
    """Extract Short script text from short.md."""
    text = path.read_text(encoding="utf-8")
    # Remove header lines, return body
    lines = [l for l in text.splitlines()
             if not l.startswith("#") and not l.startswith("_") and l.strip() != "---"]
    return "\n".join(lines).strip()


# ── Scheduling helpers ────────────────────────────────────────────────────────
def next_optimal_time(platform: str, offset_days: int = 0) -> datetime:
    """
    Calculate the next optimal posting time for a platform.
    offset_days staggers multiple posts to avoid same-day stacking.
    """
    schedule = POSTING_SCHEDULE.get(platform, POSTING_SCHEDULE["linkedin"])
    now = datetime.now()
    target = now + timedelta(days=offset_days)

    # Find next valid day
    for _ in range(14):  # look up to 2 weeks ahead
        if target.weekday() in schedule["days"]:
            scheduled = target.replace(
                hour=schedule["hour"],
                minute=schedule["minute"],
                second=0,
                microsecond=0,
            )
            if scheduled > now:
                return scheduled
        target += timedelta(days=1)

    # Fallback: tomorrow at configured time
    return (now + timedelta(days=1)).replace(
        hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0
    )


def format_schedule_time(dt: datetime) -> str:
    """Format datetime for Postiz API (ISO 8601)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ── Push to Postiz ────────────────────────────────────────────────────────────
def push_linkedin(content: str, as_draft: bool, dry_run: bool, channel_id: str = "") -> dict:
    """Push LinkedIn post to Postiz."""
    scheduled_at = None if as_draft else format_schedule_time(next_optimal_time("linkedin"))

    payload = {
        "type": "linkedin",
        "content": content,
        "status": "draft" if as_draft else "schedule",
    }
    if scheduled_at:
        payload["publishDate"] = scheduled_at
    if channel_id:
        payload["channelId"] = channel_id

    if dry_run:
        return {"dry_run": True, "platform": "linkedin", "status": payload["status"],
                "scheduled_at": scheduled_at, "content_preview": content[:100]}

    return postiz_request("POST", "/posts", payload)


def push_twitter_thread(tweets: list[str], as_draft: bool, dry_run: bool, channel_id: str = "") -> dict:
    """Push X/Twitter thread to Postiz."""
    scheduled_at = None if as_draft else format_schedule_time(next_optimal_time("twitter", offset_days=1))

    # Postiz thread format: array of tweet objects
    payload = {
        "type": "twitter",
        "content": tweets[0],           # first tweet is the main content
        "thread": [{"content": t} for t in tweets[1:]],  # rest are thread replies
        "status": "draft" if as_draft else "schedule",
    }
    if scheduled_at:
        payload["publishDate"] = scheduled_at
    if channel_id:
        payload["channelId"] = channel_id

    if dry_run:
        return {"dry_run": True, "platform": "twitter", "status": payload["status"],
                "tweet_count": len(tweets), "scheduled_at": scheduled_at,
                "first_tweet": tweets[0][:100] if tweets else ""}

    return postiz_request("POST", "/posts", payload)


def push_short_to_queue(script: str, as_draft: bool, dry_run: bool) -> dict:
    """
    Add Short script to a local queue file.
    Shorts require a video file — this queues the script for Pipeline B / manual recording.
    """
    queue_path = Path(REPURPOSED_DIR) / "shorts-queue.md"
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    entry = f"\n## {date_str}\n**Status:** {'draft' if as_draft else 'ready to record'}\n\n{script}\n\n---"

    if dry_run:
        return {"dry_run": True, "platform": "youtube_short", "action": "queued_locally",
                "note": "Shorts need a video file — script added to shorts-queue.md"}

    with open(queue_path, "a", encoding="utf-8") as f:
        f.write(entry)

    return {"platform": "youtube_short", "action": "queued", "queue_file": str(queue_path)}


# ── Folder selection ──────────────────────────────────────────────────────────
def pick_repurposed_folder() -> Path:
    """Let user pick from available repurposed folders."""
    folders = sorted(
        [f for f in Path(REPURPOSED_DIR).iterdir() if f.is_dir() and not f.name.startswith(".")],
        reverse=True
    )

    if not folders:
        rprint("[red]✗ No repurposed folders found. Run: make repurpose[/red]")
        sys.exit(1)

    rprint(f"\n[bold]Available repurposed batches:[/bold]")
    for i, folder in enumerate(folders[:10], 1):
        files = list(folder.glob("*.md"))
        rprint(f"  [cyan]{i}.[/cyan] {folder.name} [dim]({len(files)} files)[/dim]")

    rprint("")
    try:
        choice = int(input(f"Pick a number (1-{min(len(folders),10)}): ").strip())
        return folders[choice - 1]
    except (ValueError, IndexError):
        rprint("[red]✗ Invalid selection.[/red]")
        sys.exit(1)


def get_latest_folder() -> Path:
    """Auto-select most recent repurposed folder."""
    folders = sorted(
        [f for f in Path(REPURPOSED_DIR).iterdir() if f.is_dir() and not f.name.startswith(".")],
        reverse=True
    )
    if not folders:
        rprint("[red]✗ No repurposed folders found. Run: make repurpose[/red]")
        sys.exit(1)
    return folders[0]


# ── Schedule log ──────────────────────────────────────────────────────────────
def append_schedule_log(folder: Path, results: list[dict], as_draft: bool):
    """Append a record of this scheduling run to schedule-log.md."""
    log_path = Path(REPURPOSED_DIR) / "schedule-log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    mode = "DRAFT" if as_draft else "SCHEDULED"

    lines = [f"\n## {timestamp} — {mode} — {folder.name}\n"]
    for r in results:
        platform = r.get("platform", "unknown")
        status = r.get("status", r.get("action", "unknown"))
        scheduled_at = r.get("scheduled_at") or r.get("publishDate", "—")
        post_id = r.get("id") or r.get("postId", "—")
        dry = " [DRY RUN]" if r.get("dry_run") else ""
        lines.append(f"- **{platform}**: {status} | scheduled: {scheduled_at} | id: {post_id}{dry}")

    lines.append("")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ── Results table ─────────────────────────────────────────────────────────────
def print_results(results: list[dict], as_draft: bool, dry_run: bool):
    """Print a summary table of what was pushed."""
    rrule("Schedule Results")

    if RICH:
        table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0,1))
        table.add_column("Platform",   width=16)
        table.add_column("Status",     width=12)
        table.add_column("Scheduled",  width=22)
        table.add_column("ID / Note",  width=20)

        for r in results:
            platform     = r.get("platform", "unknown")
            status       = "[yellow]draft[/yellow]" if as_draft else "[green]scheduled[/green]"
            scheduled_at = r.get("scheduled_at") or r.get("publishDate", "—")
            note         = r.get("id") or r.get("postId") or r.get("note") or r.get("queue_file", "—")
            if r.get("dry_run"):
                status = "[dim]dry run[/dim]"
            if r.get("action") == "queued":
                status = "[blue]queued locally[/blue]"
            table.add_row(platform, status, str(scheduled_at)[:19], str(note)[:20])

        console.print(table)
    else:
        for r in results:
            print(f"  {r.get('platform','?'):16} | {r.get('status','?'):10} | {r.get('scheduled_at','—')}")

    if dry_run:
        rprint("\n[yellow]⚠ Dry run — nothing was actually sent to Postiz.[/yellow]")
    elif as_draft:
        rprint("\n[dim]Drafts saved. Review and approve in your Postiz dashboard before publishing.[/dim]")
    else:
        rprint("\n[green]✓ Content scheduled. Check Postiz dashboard to confirm.[/green]")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Schedule repurposed content to LinkedIn, X/Twitter, and YouTube Shorts via Postiz."
    )
    parser.add_argument("--latest",   action="store_true", help="Auto-pick most recent repurposed folder")
    parser.add_argument("--dir",      type=str,            help="Path to specific repurposed folder")
    parser.add_argument("--schedule", action="store_true", help="Schedule directly (default: save as draft)")
    parser.add_argument("--draft",    action="store_true", help="Save as draft in Postiz (default)")
    parser.add_argument("--dry-run",  action="store_true", help="Preview without calling Postiz API")
    args = parser.parse_args()

    # ── Validate environment ──
    if not CONTENT_DIR:
        print("✗ BASE_CONTENT_DIR not set. Check your .env file.")
        sys.exit(1)

    as_draft = not args.schedule  # draft is default unless --schedule is passed
    dry_run  = args.dry_run

    mode_label = "DRY RUN" if dry_run else ("SCHEDULE" if not as_draft else "DRAFT")
    rpanel(
        f"[bold green]Content Scheduler[/bold green]\n"
        f"[dim]LinkedIn · X/Twitter · YouTube Shorts Queue[/dim]\n"
        f"[dim]Mode: {mode_label}[/dim]",
        width=52
    )

    # ── Select repurposed folder ──
    if args.dir:
        folder = Path(args.dir)
        if not folder.exists():
            rprint(f"[red]✗ Folder not found: {args.dir}[/red]")
            sys.exit(1)
    elif args.latest:
        folder = get_latest_folder()
        rprint(f"\n[dim]Using: {folder.name}[/dim]")
    else:
        folder = pick_repurposed_folder()

    # ── Check required files ──
    linkedin_file = folder / "linkedin.md"
    twitter_file  = folder / "twitter.md"
    short_file    = folder / "short.md"

    missing = [f.name for f in [linkedin_file, twitter_file, short_file] if not f.exists()]
    if missing:
        rprint(f"[yellow]⚠ Missing files: {', '.join(missing)}[/yellow]")
        rprint("[dim]  Run repurpose.py first to generate all platform files.[/dim]")
        if len(missing) == 3:
            sys.exit(1)

    # ── Confirm before proceeding ──
    rprint(f"\n[bold]Ready to push:[/bold]")
    if linkedin_file.exists(): rprint(f"  [cyan]✓[/cyan] LinkedIn post")
    if twitter_file.exists():  rprint(f"  [cyan]✓[/cyan] X/Twitter thread")
    if short_file.exists():    rprint(f"  [cyan]✓[/cyan] YouTube Short (queued locally)")
    rprint(f"\n  Mode: [bold]{'draft' if as_draft else 'scheduled'}[/bold]")

    if not dry_run:
        confirm = input("\nProceed? (y/n): ").strip().lower()
        if confirm != "y":
            rprint("[yellow]Cancelled.[/yellow]")
            sys.exit(0)

    # ── Fetch Postiz channels (for channel ID mapping) ──
    channel_map = {}
    if not dry_run and POSTIZ_API_KEY:
        rprint("\n[dim]Fetching Postiz channels...[/dim]")
        channels = get_postiz_channels()
        for ch in channels:
            platform = ch.get("type", "").lower()
            channel_map[platform] = ch.get("id", "")
            rprint(f"[dim]  Found: {ch.get('name','?')} ({platform})[/dim]")

    # ── Push each platform ──
    results = []
    rprint("")

    if linkedin_file.exists():
        rprint("[dim]Pushing LinkedIn...[/dim]")
        content = parse_linkedin(linkedin_file)
        result  = push_linkedin(content, as_draft, dry_run, channel_map.get("linkedin",""))
        result["platform"] = "linkedin"
        results.append(result)

    if twitter_file.exists():
        rprint("[dim]Pushing X/Twitter thread...[/dim]")
        tweets = parse_twitter_thread(twitter_file)
        rprint(f"[dim]  {len(tweets)} tweets parsed[/dim]")
        result = push_twitter_thread(tweets, as_draft, dry_run, channel_map.get("twitter",""))
        result["platform"] = "twitter"
        results.append(result)

    if short_file.exists():
        rprint("[dim]Queuing YouTube Short script...[/dim]")
        script = parse_short_script(short_file)
        result = push_short_to_queue(script, as_draft, dry_run)
        results.append(result)

    # ── Print results ──
    rprint("")
    print_results(results, as_draft, dry_run)

    # ── Log ──
    if not dry_run:
        append_schedule_log(folder, results, as_draft)
        rprint(f"[dim]✓ Logged to: {REPURPOSED_DIR}/schedule-log.md[/dim]")


if __name__ == "__main__":
    main()
