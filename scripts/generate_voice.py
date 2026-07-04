#!/usr/bin/env python3
"""
generate_voice.py — Pipeline B: Voice Synthesis via ElevenLabs
===============================================================
Generates voiceover audio from a script using ElevenLabs.
Uses cloned voice by default, falls back to pre-built voice if
cloned voice ID is not yet configured.

Usage:
    python3 scripts/generate_voice.py                          # interactive
    python3 scripts/generate_voice.py --script <file.md>       # from script.py output
    python3 scripts/generate_voice.py --script <file.md> --auto # skip review

Flags:
    --script <file.md>   Script file from script.py output
    --short              Generate Short voiceover only (default: long-form)
    --both               Generate both long-form and Short voiceovers
    --auto               Skip review prompt, generate immediately
    --dry-run            Preview text that would be sent, no API call
    --voice <id>         Override voice ID for this run

Output:
    - $AUDIO_DIR/YYYY-MM-DD-[slug]-longform.mp3
    - $AUDIO_DIR/YYYY-MM-DD-[slug]-short.mp3
"""

import sys
import re
import argparse
from datetime import datetime
from pathlib import Path

from scripts.runtime import RuntimeConfig

runtime = RuntimeConfig(
    paths=["SCRIPTS_DIR", "AUDIO_DIR"],
    env=["ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_FALLBACK_VOICE_ID"],
)

# ElevenLabs model — eleven_multilingual_v2 is best quality
ELEVENLABS_MODEL = "eleven_multilingual_v2"

# Voice settings — tuned for conversational real estate content
VOICE_SETTINGS = {
    "stability":         0.45,   # lower = more expressive, higher = more consistent
    "similarity_boost":  0.82,   # how closely to match the voice
    "style":             0.35,   # speaking style exaggeration
    "use_speaker_boost": True,   # enhances voice clarity
}

from scripts.utils.console import rpanel, rprint, rrule


# ── Voice selection ───────────────────────────────────────────────────────────
def resolve_voice_id(override: str = "") -> tuple[str, str]:
    """
    Resolve which voice ID to use.
    Returns (voice_id, label) where label describes the source.
    """
    if override:
        return override, "override"
    if runtime.ELEVENLABS_VOICE_ID:
        return runtime.ELEVENLABS_VOICE_ID, "cloned voice"
    if runtime.ELEVENLABS_FALLBACK_VOICE_ID:
        rprint("[yellow]⚠ ELEVENLABS_VOICE_ID not set — using fallback voice[/yellow]")
        rprint("[dim]  Set ELEVENLABS_VOICE_ID in .env once you've cloned your voice[/dim]")
        return runtime.ELEVENLABS_FALLBACK_VOICE_ID, "fallback voice"

    rprint("[red]✗ No voice ID configured. Set ELEVENLABS_VOICE_ID or ELEVENLABS_FALLBACK_VOICE_ID in .env[/red]")
    sys.exit(1)


def list_available_voices() -> list[dict]:
    """Fetch available voices from ElevenLabs account."""
    import requests
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": runtime.ELEVENLABS_API_KEY},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("voices", [])
    except Exception as e:
        rprint(f"[yellow]⚠ Could not fetch voices: {e}[/yellow]")
        return []


# ── Script parsing ────────────────────────────────────────────────────────────
def extract_longform_text(script_path: Path) -> tuple[str, str]:
    """
    Extract clean spoken text from a script.py output file.
    Returns (title, clean_text).
    Strips stage directions, B-roll cues, graphic cues, and section markers.
    """
    text = script_path.read_text(encoding="utf-8")

    # Extract title
    title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = title_match.group(1) if title_match else script_path.stem

    # Extract long-form section
    longform_match = re.search(
        r"## Long-form script.*?\n(.+?)(?=\n---\n## |\Z)",
        text, re.DOTALL
    )
    raw = longform_match.group(1) if longform_match else text

    clean = clean_script_for_voice(raw)
    return title, clean


def extract_short_text(script_path: Path) -> tuple[str, str]:
    """
    Extract Short script text from a script.py output file.
    Returns (title, clean_text).
    """
    text = script_path.read_text(encoding="utf-8")

    title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = title_match.group(1) if title_match else script_path.stem

    short_match = re.search(
        r"## Short script.*?\n(.+?)(?=\n---\n## |\Z)",
        text, re.DOTALL
    )
    raw = short_match.group(1) if short_match else ""

    if not raw:
        rprint("[yellow]⚠ No Short script section found in file[/yellow]")
        return title, ""

    clean = clean_script_for_voice(raw)
    return title, clean


def clean_script_for_voice(raw: str) -> str:
    """
    Strip everything that shouldn't be spoken aloud.
    Removes: section markers, B-roll cues, graphic cues, verify flags,
    markdown headers, checklist items, metadata blocks.
    """
    text = raw

    # Remove section markers like [HOOK], [INTRO], [SECTION_1: title], [CTA]
    text = re.sub(r"\[HOOK\]|\[INTRO\]|\[RECAP\]|\[CTA\]", "", text)
    text = re.sub(r"\[SECTION_\d+:[^\]]*\]", "", text)

    # Remove production cues
    text = re.sub(r"\[B-ROLL[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[GRAPHIC:[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[verify before filming\]", "", text, flags=re.IGNORECASE)

    # Remove markdown headers
    text = re.sub(r"^#{1,6}\s+.+$", "", text, flags=re.MULTILINE)

    # Remove checklist items
    text = re.sub(r"^- \[[ x]\].+$", "", text, flags=re.MULTILINE)

    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)

    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)

    # Remove horizontal rules
    text = re.sub(r"^---+$", "", text, flags=re.MULTILINE)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def estimate_duration(text: str) -> str:
    """Estimate spoken duration from word count (~150 words/minute)."""
    words = len(text.split())
    minutes = words / 150
    if minutes < 1:
        return f"~{int(minutes * 60)} seconds"
    return f"~{minutes:.1f} minutes ({words:,} words)"


# ── ElevenLabs API ────────────────────────────────────────────────────────────
def generate_audio(
    text: str,
    voice_id: str,
    output_path: Path,
    dry_run: bool = False,
) -> bool:
    """
    Call ElevenLabs TTS API and save audio to output_path.
    Returns True on success.
    """
    import requests

    if dry_run:
        rprint(f"[dim][DRY RUN] Would generate audio:[/dim]")
        rprint(f"[dim]  Voice ID: {voice_id}[/dim]")
        rprint(f"[dim]  Output:   {output_path}[/dim]")
        rprint(f"[dim]  Text ({len(text)} chars):[/dim]")
        rprint(f"[dim]  {text[:200]}...[/dim]")
        return True

    if not runtime.ELEVENLABS_API_KEY:
        rprint("[red]✗ ELEVENLABS_API_KEY not set in .env[/red]")
        return False

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": VOICE_SETTINGS,
    }

    headers = {
        "xi-api-key": runtime.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    try:
        rprint(f"[dim]Calling ElevenLabs API ({len(text):,} chars)...[/dim]")
        resp = requests.post(url, json=payload, headers=headers, timeout=120, stream=True)
        resp.raise_for_status()

        # Stream audio to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        file_size_mb = output_path.stat().st_size / 1024 / 1024
        rprint(f"[green]✓ Audio saved: {output_path.name} ({file_size_mb:.1f} MB)[/green]")
        return True

    except requests.exceptions.HTTPError as e:
        rprint(f"[red]✗ ElevenLabs API error {resp.status_code}: {resp.text[:200]}[/red]")
        return False
    except Exception as e:
        rprint(f"[red]✗ Audio generation failed: {e}[/red]")
        return False


def check_usage() -> dict:
    """Check ElevenLabs character usage for current billing period."""
    import requests
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": runtime.ELEVENLABS_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        used      = data.get("character_count", 0)
        limit     = data.get("character_limit", 0)
        remaining = limit - used
        return {
            "used":      used,
            "limit":     limit,
            "remaining": remaining,
            "pct_used":  round(used / limit * 100, 1) if limit > 0 else 0,
        }
    except Exception:
        return {}


# ── Script file selection ─────────────────────────────────────────────────────
def pick_script_file() -> Path:
    """Let user pick from available script files."""
    scripts = sorted(Path(runtime.SCRIPTS_DIR).glob("*-script.md"), reverse=True)
    if not scripts:
        rprint("[red]✗ No script files found. Run: make script[/red]")
        sys.exit(1)

    rprint(f"\n[bold]Available scripts:[/bold]")
    for i, s in enumerate(scripts[:10], 1):
        rprint(f"  [cyan]{i}.[/cyan] {s.name}")

    rprint("")
    try:
        choice = int(input(f"Pick a number (1-{min(len(scripts),10)}): ").strip())
        return scripts[choice - 1]
    except (ValueError, IndexError):
        rprint("[red]✗ Invalid selection.[/red]")
        sys.exit(1)


def get_latest_script() -> Path:
    """Auto-select most recent script file."""
    scripts = sorted(Path(runtime.SCRIPTS_DIR).glob("*-script.md"), reverse=True)
    if not scripts:
        rprint("[red]✗ No script files found. Run: make script[/red]")
        sys.exit(1)
    return scripts[0]


# ── Review step ───────────────────────────────────────────────────────────────
def review_text(label: str, text: str, auto: bool) -> bool:
    """
    Show text preview and optionally ask for confirmation.
    Returns True to proceed, False to skip.
    """
    rrule(f"Preview — {label}")
    preview = text[:600]
    rprint(preview)
    if len(text) > 600:
        rprint(f"[dim]... ({len(text):,} total chars — {estimate_duration(text)})[/dim]")
    else:
        rprint(f"[dim]({len(text):,} chars — {estimate_duration(text)})[/dim]")
    rprint("")

    if auto:
        return True

    confirm = input("Generate audio for this? (y/n/skip): ").strip().lower()
    return confirm in ("y", "yes")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generate voiceover audio from a script using ElevenLabs."
    )
    parser.add_argument("--script",  type=str,            help="Path to script.py output .md file")
    parser.add_argument("--latest",  action="store_true", help="Auto-pick most recent script file")
    parser.add_argument("--short",   action="store_true", help="Generate Short voiceover only")
    parser.add_argument("--both",    action="store_true", help="Generate both long-form and Short")
    parser.add_argument("--auto",    action="store_true", help="Skip review prompts")
    parser.add_argument("--dry-run", action="store_true", help="Preview without calling API")
    parser.add_argument("--voice",   type=str,            help="Override voice ID for this run")
    parser.add_argument("--voices",  action="store_true", help="List available voices and exit")
    args = parser.parse_args()

    # ── Validate ──

    # ── List voices mode ──
    if args.voices:
        rprint("\n[bold]Available ElevenLabs voices:[/bold]")
        voices = list_available_voices()
        for v in voices:
            cloned = " [cloned]" if v.get("category") == "cloned" else ""
            rprint(f"  {v.get('voice_id','?'):25} {v.get('name','?')}{cloned}")
        sys.exit(0)

    rpanel(
        "[bold green]Voice Generator[/bold green]\n"
        "[dim]ElevenLabs · Long-form + Shorts[/dim]",
        width=46,
    )

    # ── Check usage ──
    if not args.dry_run and runtime.ELEVENLABS_API_KEY:
        usage = check_usage()
        if usage:
            color = "red" if usage["pct_used"] > 80 else "yellow" if usage["pct_used"] > 60 else "green"
            rprint(f"\n[dim]ElevenLabs usage: [{color}]{usage['used']:,}/{usage['limit']:,} chars ({usage['pct_used']}% used)[/{color}][/dim]")

    # ── Resolve voice ──
    voice_id, voice_label = resolve_voice_id(args.voice or "")
    rprint(f"[dim]Voice: {voice_label} ({voice_id})[/dim]\n")

    # ── Select script ──
    if args.script:
        script_path = Path(args.script)
        if not script_path.exists():
            # Try finding in SCRIPTS_DIR
            matches = list(Path(runtime.SCRIPTS_DIR).glob(f"*{Path(args.script).stem}*"))
            if matches:
                script_path = sorted(matches)[-1]
            else:
                rprint(f"[red]✗ Script not found: {args.script}[/red]")
                sys.exit(1)
    elif args.latest:
        script_path = get_latest_script()
        rprint(f"[dim]Using: {script_path.name}[/dim]")
    else:
        script_path = pick_script_file()

    # ── Determine what to generate ──
    do_longform = not args.short   # default is long-form
    do_short    = args.short or args.both

    # ── Build output paths ──
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug     = re.sub(r"[^a-z0-9]+", "-", script_path.stem.lower())[:40].strip("-")
    # Remove trailing -script from slug if present
    slug     = re.sub(r"-script$", "", slug)

    audio_dir = Path(runtime.AUDIO_DIR)

    results = []

    # ── Long-form voiceover ──
    if do_longform:
        rprint("\n[bold]Long-form voiceover[/bold]")
        title, longform_text = extract_longform_text(script_path)

        if not longform_text:
            rprint("[yellow]⚠ No long-form script text found[/yellow]")
        else:
            rprint(f"[dim]Title: {title}[/dim]")
            proceed = review_text("Long-form", longform_text, args.auto or args.dry_run)

            if proceed:
                out_path = audio_dir / f"{date_str}-{slug}-longform.mp3"
                success  = generate_audio(longform_text, voice_id, out_path, args.dry_run)
                results.append({
                    "type":    "longform",
                    "success": success,
                    "path":    str(out_path),
                    "chars":   len(longform_text),
                    "duration": estimate_duration(longform_text),
                })
            else:
                rprint("[dim]Skipped long-form.[/dim]")

    # ── Short voiceover ──
    if do_short:
        rprint("\n[bold]Short voiceover[/bold]")
        title, short_text = extract_short_text(script_path)

        if not short_text:
            rprint("[yellow]⚠ No Short script section found in file[/yellow]")
            rprint("[dim]  Check shorts-queue.md for queued Short scripts[/dim]")
        else:
            proceed = review_text("Short", short_text, args.auto or args.dry_run)

            if proceed:
                out_path = audio_dir / f"{date_str}-{slug}-short.mp3"
                success  = generate_audio(short_text, voice_id, out_path, args.dry_run)
                results.append({
                    "type":    "short",
                    "success": success,
                    "path":    str(out_path),
                    "chars":   len(short_text),
                    "duration": estimate_duration(short_text),
                })
            else:
                rprint("[dim]Skipped Short.[/dim]")

    # ── Summary ──
    if results:
        rrule("Summary")
        for r in results:
            status = "[green]✓[/green]" if r["success"] else "[red]✗[/red]"
            dry    = " [DRY RUN]" if args.dry_run else ""
            rprint(f"  {status} {r['type']:10} | {r['duration']:20} | {r['path']}{dry}")

        if not args.dry_run:
            succeeded = [r for r in results if r["success"]]
            if succeeded:
                rprint(f"\n[dim]Audio files saved to: {runtime.AUDIO_DIR}[/dim]")
                rprint(f"[dim]Next step: run generate_video.py to render the video[/dim]")
                rprint(f"[dim]           make generate-video[/dim]")
    else:
        rprint("\n[yellow]No audio generated.[/yellow]")


if __name__ == "__main__":
    main()
