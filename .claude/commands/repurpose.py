#!/usr/bin/env python3
"""
repurpose.py — Pipeline A: Content Repurposing
===============================================
Repurposes a YouTube video into LinkedIn, X/Twitter, Short, and Newsletter
content. Accepts a YouTube URL, transcript text file, or saved script.py file.

Usage:
    python3 scripts/repurpose.py                          # interactive mode
    python3 scripts/repurpose.py --url <youtube_url>      # from YouTube URL
    python3 scripts/repurpose.py --transcript <file.txt>  # from transcript file
    python3 scripts/repurpose.py --script <file.md>       # from script.py output

Output:
    - $REPURPOSED_DIR/YYYY-MM-DD-[slug]/repurposed-combined.md
    - $REPURPOSED_DIR/YYYY-MM-DD-[slug]/linkedin.md
    - $REPURPOSED_DIR/YYYY-MM-DD-[slug]/twitter.md
    - $REPURPOSED_DIR/YYYY-MM-DD-[slug]/short.md
    - $REPURPOSED_DIR/YYYY-MM-DD-[slug]/newsletter.md
"""

import os
import sys
import re
import json
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()

CONTENT_DIR    = os.getenv("BASE_CONTENT_DIR", "")
SCRIPTS_DIR    = os.getenv("SCRIPTS_DIR",    os.path.join(CONTENT_DIR, "scripts"))
REPURPOSED_DIR = os.getenv("REPURPOSED_DIR", os.path.join(CONTENT_DIR, "repurposed"))
CHANNEL_NAME   = os.getenv("CHANNEL_NAME", "realestate-channel")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# ── Rich setup ────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.markdown import Markdown
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None

def rprint(msg):  console.print(msg) if RICH else print(msg)
def rpanel(msg, **kw): console.print(Panel(msg, **kw)) if RICH else print(f"\n{'='*60}\n{msg}\n{'='*60}")
def rrule(msg=""): console.print(Rule(msg)) if RICH else print(f"\n--- {msg} ---")


# ── Anthropic API ─────────────────────────────────────────────────────────────
def call_claude(prompt: str, system: str, max_tokens: int = 1000) -> str:
    import requests

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return "\n".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
    except requests.exceptions.RequestException as e:
        print(f"✗ Claude API error: {e}")
        sys.exit(1)


def build_system_prompt() -> str:
    return f"""You are the content repurposing strategist for {CHANNEL_NAME}, a YouTube channel
about real estate, mortgages, and loans.

Audience: Intermediate — researched but haven't done a deal yet.
Tone: Conversational and relatable. Like a knowledgeable friend, not a professor or hype guy.

Platform-specific rules:
- LinkedIn: slightly more professional, lead with a data point or counterintuitive observation,
  warm but authoritative, 200-250 words, no hashtag stuffing (max 3 relevant hashtags)
- X/Twitter: punchy, each tweet standalone, 5-7 tweets, last tweet = CTA to watch the video,
  threads feel native not copy-pasted, no hashtags except 1 on the last tweet
- YouTube Short: reframe the single most surprising/counterintuitive moment — NOT a summary,
  45-60 seconds spoken (~120-150 words), hook on first line, end with "full breakdown on the channel"
- Newsletter: go one level deeper than the video — add context you didn't have time to cover,
  350-400 words, conversational, structured with a clear takeaway at the end

Never use: "game-changer", "deep dive", "unpack", "Furthermore", "Moreover", "In conclusion"
Never start any piece with "Hey guys" or "Welcome back"
Each piece must feel native to its platform — not like a repaste of the video script."""


# ── Input: fetch transcript from YouTube URL ──────────────────────────────────
def fetch_youtube_transcript(url: str) -> tuple[str, str]:
    """
    Fetch transcript and title from a YouTube URL.
    Returns (title, transcript_text).
    Falls back to description if transcript unavailable.
    """
    # Extract video ID
    vid_id = None
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            vid_id = match.group(1)
            break

    if not vid_id:
        rprint("[red]✗ Could not extract video ID from URL.[/red]")
        sys.exit(1)

    rprint(f"[dim]Video ID: {vid_id}[/dim]")

    # Try youtube-transcript-api first (no API key needed)
    title = f"Video {vid_id}"
    transcript_text = ""

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript = YouTubeTranscriptApi.get_transcript(vid_id)
        transcript_text = " ".join(t["text"] for t in transcript)
        rprint(f"[green]✓ Transcript fetched ({len(transcript_text)} chars)[/green]")
    except ImportError:
        rprint("[yellow]⚠ youtube-transcript-api not installed.[/yellow]")
        rprint("[dim]  Install with: pip3 install youtube-transcript-api[/dim]")
    except Exception as e:
        rprint(f"[yellow]⚠ Could not fetch transcript: {e}[/yellow]")

    # Fetch title via YouTube Data API if key is set
    if YOUTUBE_API_KEY:
        try:
            import requests
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "snippet", "id": vid_id, "key": YOUTUBE_API_KEY},
                timeout=10,
            )
            data = resp.json()
            items = data.get("items", [])
            if items:
                title = items[0]["snippet"]["title"]
                rprint(f"[green]✓ Title: {title}[/green]")
                # Use description as fallback if no transcript
                if not transcript_text:
                    transcript_text = items[0]["snippet"].get("description", "")
                    rprint("[yellow]⚠ Using video description as fallback (no transcript)[/yellow]")
        except Exception as e:
            rprint(f"[yellow]⚠ Could not fetch video metadata: {e}[/yellow]")

    if not transcript_text:
        rprint("[red]✗ No transcript or description available. Try --transcript or --script mode.[/red]")
        sys.exit(1)

    return title, transcript_text


def load_transcript_file(path: str) -> tuple[str, str]:
    """Load transcript from a .txt file. Returns (filename_as_title, text)."""
    p = Path(path)
    if not p.exists():
        rprint(f"[red]✗ File not found: {path}[/red]")
        sys.exit(1)
    text = p.read_text(encoding="utf-8")
    title = p.stem.replace("-", " ").replace("_", " ").title()
    rprint(f"[green]✓ Loaded transcript: {p.name} ({len(text)} chars)[/green]")
    return title, text


def load_script_file(path: str) -> tuple[str, str]:
    """Load a script.py output .md file. Returns (title, script_text)."""
    p = Path(path)
    if not p.exists():
        # Try searching SCRIPTS_DIR for partial match
        matches = list(Path(SCRIPTS_DIR).glob(f"*{Path(path).stem}*"))
        if matches:
            p = sorted(matches)[-1]
            rprint(f"[dim]Found: {p.name}[/dim]")
        else:
            rprint(f"[red]✗ Script file not found: {path}[/red]")
            sys.exit(1)

    text = p.read_text(encoding="utf-8")

    # Extract title from first heading
    title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = title_match.group(1) if title_match else p.stem

    # Extract long-form section
    longform_match = re.search(
        r"## Long-form script.*?\n(.+?)(?=\n---|\n## Short script|$)",
        text, re.DOTALL
    )
    script_text = longform_match.group(1).strip() if longform_match else text

    rprint(f"[green]✓ Loaded script: {p.name}[/green]")
    return title, script_text


def pick_latest_script() -> tuple[str, str]:
    """Auto-pick the most recent script file from SCRIPTS_DIR."""
    scripts = sorted(Path(SCRIPTS_DIR).glob("*-script.md"), reverse=True)
    if not scripts:
        rprint("[red]✗ No script files found. Run: make script[/red]")
        sys.exit(1)

    rprint(f"\n[bold]Available scripts:[/bold]")
    for i, s in enumerate(scripts[:10], 1):
        rprint(f"  [cyan]{i}.[/cyan] {s.name}")

    rprint("")
    try:
        choice = int(input(f"Pick a number (1-{min(len(scripts),10)}): ").strip())
        return load_script_file(str(scripts[choice - 1]))
    except (ValueError, IndexError):
        rprint("[red]✗ Invalid selection.[/red]")
        sys.exit(1)


# ── Repurposing generators ────────────────────────────────────────────────────
def generate_linkedin(title: str, content: str) -> str:
    prompt = f"""Repurpose this YouTube content about "{title}" into a LinkedIn post.

CONTENT:
{content[:4000]}

Rules:
- 200-250 words
- Lead with a data point, surprising stat, or counterintuitive observation — not an intro
- Professional but warm — like a knowledgeable colleague sharing an insight
- Short paragraphs (2-3 sentences max), white space is your friend on LinkedIn
- End with a question that invites comments
- Max 3 hashtags at the very end, relevant and specific (e.g. #RealEstate #Mortgages #HomeBuying)
- Do NOT start with "I just posted" or reference the YouTube video in the opening

Write the LinkedIn post now, no preamble:"""
    return call_claude(prompt, build_system_prompt())


def generate_twitter(title: str, content: str) -> str:
    prompt = f"""Repurpose this YouTube content about "{title}" into an X/Twitter thread.

CONTENT:
{content[:4000]}

Rules:
- 5-7 tweets
- Each tweet must stand alone — someone reading just that tweet gets value
- Tweet 1: the hook — most surprising or counterintuitive insight, no setup
- Tweets 2-5: one concrete point each, build on each other
- Tweet 6-7 (optional): practical takeaway or common mistake to avoid
- Last tweet: CTA — "Full breakdown: [link]" + 1 relevant hashtag
- No hashtags except on the last tweet
- Under 280 characters per tweet
- Number each tweet: 1/ 2/ 3/ etc.

Write the full thread now, no preamble:"""
    return call_claude(prompt, build_system_prompt())


def generate_short(title: str, content: str) -> str:
    prompt = f"""Repurpose this YouTube content about "{title}" into a YouTube Short script.

CONTENT:
{content[:4000]}

Rules:
- 45-60 seconds spoken (~120-150 words)
- Find the SINGLE most surprising, counterintuitive, or high-stakes moment — build around that
- Do NOT summarize the video — this is a standalone insight, not a preview
- First line IS the hook — no warm-up, no intro
- End with: "Full breakdown on the channel" — nothing more
- Format with [HOOK], [BODY], [CTA] markers

Write the Short script now, no preamble:"""
    return call_claude(prompt, build_system_prompt())


def generate_newsletter(title: str, content: str) -> str:
    prompt = f"""Repurpose this YouTube content about "{title}" into a newsletter section.

CONTENT:
{content[:4000]}

Rules:
- 350-400 words
- Go ONE LEVEL DEEPER than the video — add context, nuance, or an angle you didn't have
  time to cover on camera. The newsletter reader should feel they got more than the viewer.
- Structure: hook opening → 2-3 substantive points → clear takeaway or action step
- Conversational but slightly more considered than spoken word
- Include a "This week's bottom line:" section at the end (2-3 sentences, plain language)
- No sign-off, no "subscribe" CTA — this is a section within a larger newsletter

Write the newsletter section now, no preamble:"""
    return call_claude(prompt, build_system_prompt())


# ── Save output ───────────────────────────────────────────────────────────────
def save_repurposed(
    title: str,
    linkedin: str,
    twitter: str,
    short: str,
    newsletter: str,
    source_mode: str,
) -> str:
    """Save all repurposed content. Returns output directory path."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower())[:40].strip("-")
    out_dir = Path(REPURPOSED_DIR) / f"{date_str}-{slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Individual platform files ──
    platform_files = {
        "linkedin.md": (
            f"# LinkedIn Post — {title}\n"
            f"_Generated: {timestamp} | Source: {source_mode}_\n\n"
            f"---\n\n{linkedin}\n"
        ),
        "twitter.md": (
            f"# X/Twitter Thread — {title}\n"
            f"_Generated: {timestamp} | Source: {source_mode}_\n\n"
            f"---\n\n{twitter}\n"
        ),
        "short.md": (
            f"# YouTube Short Script — {title}\n"
            f"_Generated: {timestamp} | Source: {source_mode}_\n\n"
            f"---\n\n{short}\n"
        ),
        "newsletter.md": (
            f"# Newsletter Section — {title}\n"
            f"_Generated: {timestamp} | Source: {source_mode}_\n\n"
            f"---\n\n{newsletter}\n"
        ),
    }

    for filename, content in platform_files.items():
        (out_dir / filename).write_text(content, encoding="utf-8")

    # ── Combined file ──
    combined = f"""# Repurposed Content — {title}

**Generated:** {timestamp}
**Source:** {source_mode}

---

## LinkedIn Post

{linkedin}

---

## X/Twitter Thread

{twitter}

---

## YouTube Short Script

{short}

---

## Newsletter Section

{newsletter}

---

## Publishing checklist

- [ ] Review LinkedIn post — edit for personal voice
- [ ] Review Twitter thread — verify each tweet stands alone
- [ ] Review Short script — record or add to HeyGen queue
- [ ] Review newsletter section — paste into newsletter draft
- [ ] Schedule via Postiz: `make schedule`
"""
    (out_dir / "repurposed-combined.md").write_text(combined, encoding="utf-8")

    return str(out_dir)


# ── Terminal preview ──────────────────────────────────────────────────────────
def print_preview(title: str, linkedin: str, twitter: str, short: str, newsletter: str):
    rpanel(f"[bold green]Repurposed: {title}[/bold green]", style="green")

    rrule("LinkedIn")
    rprint(linkedin[:600] + ("\n[dim]...[/dim]" if len(linkedin) > 600 else ""))

    rrule("X/Twitter Thread")
    rprint(twitter[:600] + ("\n[dim]...[/dim]" if len(twitter) > 600 else ""))

    rrule("YouTube Short")
    rprint(short)

    rrule("Newsletter")
    rprint(newsletter[:600] + ("\n[dim]...[/dim]" if len(newsletter) > 600 else ""))


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Repurpose a YouTube video into LinkedIn, X, Short, and Newsletter content."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url",        type=str, help="YouTube video URL")
    group.add_argument("--transcript", type=str, help="Path to transcript .txt file")
    group.add_argument("--script",     type=str, help="Path to script.py output .md file")
    parser.add_argument("--no-save",   action="store_true", help="Terminal output only")
    args = parser.parse_args()

    # ── Validate environment ──
    if not CONTENT_DIR:
        print("✗ BASE_CONTENT_DIR not set. Check your .env file.")
        sys.exit(1)

    rpanel(
        "[bold green]Content Repurposer[/bold green]\n"
        "[dim]LinkedIn · X/Twitter · Short · Newsletter[/dim]",
        width=52
    )

    # ── Get source content ──
    if args.url:
        rprint(f"\n[dim]Fetching transcript from URL...[/dim]")
        title, content = fetch_youtube_transcript(args.url)
        source_mode = f"YouTube URL: {args.url}"

    elif args.transcript:
        title, content = load_transcript_file(args.transcript)
        source_mode = f"Transcript file: {args.transcript}"

    elif args.script:
        title, content = load_script_file(args.script)
        source_mode = f"Script file: {args.script}"

    else:
        # Interactive mode
        rprint("\nChoose your input source:")
        rprint("  [cyan]1.[/cyan] YouTube video URL")
        rprint("  [cyan]2.[/cyan] Transcript text file")
        rprint("  [cyan]3.[/cyan] Script file from script.py")
        rprint("")
        choice = input("Choice (1/2/3): ").strip()

        if choice == "1":
            url = input("YouTube URL: ").strip()
            rprint("[dim]Fetching transcript...[/dim]")
            title, content = fetch_youtube_transcript(url)
            source_mode = f"YouTube URL: {url}"
        elif choice == "2":
            path = input("Path to transcript file: ").strip()
            title, content = load_transcript_file(path)
            source_mode = f"Transcript file: {path}"
        else:
            title, content = pick_latest_script()
            source_mode = "Script file"

    rprint(f"\n[bold]Title:[/bold] {title}")
    rprint(f"[dim]Content length: {len(content)} chars[/dim]\n")

    # ── Generate all four ──
    rprint("[dim]Generating LinkedIn post...[/dim]")
    linkedin = generate_linkedin(title, content)

    rprint("[dim]Generating X/Twitter thread...[/dim]")
    twitter = generate_twitter(title, content)

    rprint("[dim]Generating Short script...[/dim]")
    short = generate_short(title, content)

    rprint("[dim]Generating newsletter section...[/dim]\n")
    newsletter = generate_newsletter(title, content)

    # ── Output ──
    print_preview(title, linkedin, twitter, short, newsletter)

    # ── Save ──
    if not args.no_save:
        out_dir = save_repurposed(title, linkedin, twitter, short, newsletter, source_mode)
        rprint(f"\n[green]✓ Saved to:[/green] {out_dir}")
        rprint(f"[dim]  repurposed-combined.md + 4 platform files[/dim]")


if __name__ == "__main__":
    main()
