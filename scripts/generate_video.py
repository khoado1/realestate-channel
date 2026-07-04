#!/usr/bin/env python3
"""
generate_video.py — Pipeline B: Video Generation
=================================================
Generates videos using:
  - HeyGen avatar (long-form): pairs with ElevenLabs audio
  - HyperFrames animated (Shorts): motion graphics style

Usage:
    python3 scripts/generate_video.py                         # interactive
    python3 scripts/generate_video.py --latest                # auto-pick latest audio
    python3 scripts/generate_video.py --longform <audio.mp3>  # specific long-form file
    python3 scripts/generate_video.py --short <audio.mp3>     # specific Short file
    python3 scripts/generate_video.py --both --latest         # generate both
    python3 scripts/generate_video.py --latest --auto         # skip review prompts
    python3 scripts/generate_video.py --dry-run               # preview, no API calls

Flags:
    --latest      Auto-pick most recent audio files from $AUDIO_DIR
    --longform    Path to long-form .mp3 file
    --short       Path to Short .mp3 file
    --both        Generate both long-form (HeyGen) and Short (HyperFrames)
    --auto        Skip confirmation prompts
    --dry-run     Preview payloads without calling APIs
    --status      Check render status of a pending job by ID

Output:
    - $LONGFORM_DIR/YYYY-MM-DD-[slug]-longform.mp4  (HeyGen)
    - $SHORTS_DIR/YYYY-MM-DD-[slug]-short.mp4       (HyperFrames)
    - $VIDEO_DIR/render-log.md                  (job tracking)
"""

import os
import sys
import re
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

from scripts.runtime import RuntimeConfig

runtime = RuntimeConfig(
    path_specs=[
        ("SCRIPTS_DIR", lambda content_dir: os.path.join(content_dir, "scripts")),
        ("VIDEO_DIR", ""),
        ("AUDIO_DIR", ""),
        ("LONGFORM_DIR", ""),
        ("SHORTS_DIR", ""),
    ],
)

HEYGEN_API_KEY   = os.getenv("HEYGEN_API_KEY", "")
HEYGEN_AVATAR_ID = os.getenv("HEYGEN_AVATAR_ID", "")         # custom avatar (set after creation)

ELEVENLABS_API_KEY   = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID  = os.getenv("ELEVENLABS_VOICE_ID", "")

HEYGEN_BASE_URL      = "https://api.heygen.com"
HYPERFRAMES_BASE_URL = "https://api.hyperframes.ai/v1"  # update if endpoint changes

RENDER_LOG = Path(runtime.VIDEO_DIR) / "render-log.md" if runtime.VIDEO_DIR else Path("render-log.md")

# ── HeyGen defaults ───────────────────────────────────────────────────────────
# Stock avatar used as fallback until custom avatar is created
HEYGEN_STOCK_AVATAR_ID   = "Daisy-inskirt-20220818"   # professional, neutral
HEYGEN_STOCK_AVATAR_STYLE = "normal"
HEYGEN_VIDEO_WIDTH        = 1920
HEYGEN_VIDEO_HEIGHT       = 1080
HEYGEN_BACKGROUND_COLOR   = "#f5f5f5"

# Shorts format
SHORTS_WIDTH  = 1080
SHORTS_HEIGHT = 1920

# Poll interval for render status checks (seconds)
POLL_INTERVAL = 15
POLL_TIMEOUT  = 1800   # 30 minutes max wait

# ── Rich setup ────────────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.rule import Rule
    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None

def rprint(msg):       console.print(msg) if RICH else print(msg)
def rpanel(msg, **kw): console.print(Panel(msg, **kw)) if RICH else print(f"\n{'='*60}\n{msg}\n{'='*60}")
def rrule(msg=""):     console.print(Rule(msg)) if RICH else print(f"\n--- {msg} ---")


# ── HeyGen API ────────────────────────────────────────────────────────────────
def heygen_request(method: str, endpoint: str, payload: dict = None) -> dict:
    """Make a HeyGen API request."""
    import requests

    if not HEYGEN_API_KEY:
        rprint("[red]✗ HEYGEN_API_KEY not set in .env[/red]")
        sys.exit(1)

    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json",
    }
    url = f"{HEYGEN_BASE_URL}/{endpoint.lstrip('/')}"

    try:
        resp = requests.request(
            method.upper(), url,
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        rprint(f"[red]✗ HeyGen API error {resp.status_code}: {resp.text[:300]}[/red]")
        raise
    except requests.exceptions.RequestException as e:
        rprint(f"[red]✗ HeyGen connection error: {e}[/red]")
        raise


def resolve_avatar_id() -> tuple[str, str]:
    """
    Resolve which HeyGen avatar to use.
    Returns (avatar_id, label).
    """
    if HEYGEN_AVATAR_ID:
        return HEYGEN_AVATAR_ID, "custom avatar"
    rprint("[yellow]⚠ HEYGEN_AVATAR_ID not set — using stock avatar[/yellow]")
    rprint("[dim]  Set HEYGEN_AVATAR_ID in .env after creating your avatar at heygen.com[/dim]")
    return HEYGEN_STOCK_AVATAR_ID, f"stock avatar ({HEYGEN_STOCK_AVATAR_ID})"


def upload_audio_to_heygen(audio_path: Path) -> str:
    """
    Upload a local .mp3 file to HeyGen and return the asset ID.
    HeyGen requires audio to be hosted — this uploads it to their asset store.
    """
    import requests

    rprint(f"[dim]Uploading audio to HeyGen asset store...[/dim]")

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "audio/mpeg",
    }

    try:
        resp = requests.post(
            f"{HEYGEN_BASE_URL}/v1/asset",
            headers=headers,
            data=audio_data,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        asset_id = data.get("data", {}).get("id") or data.get("id", "")
        if not asset_id:
            rprint(f"[red]✗ No asset ID in HeyGen response: {data}[/red]")
            sys.exit(1)
        rprint(f"[green]✓ Audio uploaded: {asset_id}[/green]")
        return asset_id
    except Exception as e:
        rprint(f"[red]✗ Audio upload failed: {e}[/red]")
        sys.exit(1)


def submit_heygen_video(
    audio_path: Path,
    avatar_id: str,
    title: str,
    dry_run: bool = False,
) -> str:
    """
    Submit a HeyGen video generation job.
    Returns job_id (or 'dry_run' if dry_run=True).
    """
    file_size_mb = audio_path.stat().st_size / 1024 / 1024

    rprint(f"\n[bold]HeyGen long-form render[/bold]")
    rprint(f"  Avatar:  {avatar_id}")
    rprint(f"  Audio:   {audio_path.name} ({file_size_mb:.1f} MB)")
    rprint(f"  Format:  {HEYGEN_VIDEO_WIDTH}x{HEYGEN_VIDEO_HEIGHT}")

    if dry_run:
        rprint("[dim][DRY RUN] Would submit HeyGen job — skipping API call[/dim]")
        return "dry_run_job_id"

    # Upload audio first
    audio_asset_id = upload_audio_to_heygen(audio_path)

    # Build HeyGen v2 video payload
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": HEYGEN_STOCK_AVATAR_STYLE,
                },
                "voice": {
                    "type": "audio",
                    "audio_asset_id": audio_asset_id,
                },
                "background": {
                    "type": "color",
                    "value": HEYGEN_BACKGROUND_COLOR,
                },
            }
        ],
        "dimension": {
            "width":  HEYGEN_VIDEO_WIDTH,
            "height": HEYGEN_VIDEO_HEIGHT,
        },
        "caption": False,   # set True to auto-add captions
        "title":   title[:50],
    }

    try:
        data = heygen_request("POST", "/v2/video/generate", payload)
        job_id = data.get("data", {}).get("video_id") or data.get("video_id", "")
        if not job_id:
            rprint(f"[red]✗ No job ID in HeyGen response: {data}[/red]")
            sys.exit(1)
        rprint(f"[green]✓ HeyGen job submitted: {job_id}[/green]")
        return job_id
    except Exception as e:
        rprint(f"[red]✗ HeyGen submission failed: {e}[/red]")
        sys.exit(1)


def poll_heygen_status(job_id: str, output_path: Path) -> bool:
    """
    Poll HeyGen until the video is ready, then download it.
    Returns True on success.
    """
    import requests

    rprint(f"\n[dim]Polling HeyGen render status (job: {job_id})...[/dim]")
    rprint(f"[dim]This typically takes 5-20 minutes for long-form content.[/dim]\n")

    start = time.time()

    if RICH:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Rendering...", total=None)

            while time.time() - start < POLL_TIMEOUT:
                time.sleep(POLL_INTERVAL)
                try:
                    data = heygen_request("GET", f"/v1/video_status.get?video_id={job_id}")
                    status = data.get("data", {}).get("status", "")
                    progress.update(task, description=f"Rendering... [{status}]")

                    if status == "completed":
                        video_url = data.get("data", {}).get("video_url", "")
                        if video_url:
                            progress.stop()
                            return download_video(video_url, output_path)
                        break

                    elif status == "failed":
                        error = data.get("data", {}).get("error", {})
                        progress.stop()
                        rprint(f"[red]✗ HeyGen render failed: {error}[/red]")
                        return False

                except Exception as e:
                    progress.update(task, description=f"Polling error: {e} — retrying...")
    else:
        while time.time() - start < POLL_TIMEOUT:
            time.sleep(POLL_INTERVAL)
            try:
                data = heygen_request("GET", f"/v1/video_status.get?video_id={job_id}")
                status = data.get("data", {}).get("status", "")
                elapsed = int(time.time() - start)
                print(f"  [{elapsed}s] Status: {status}")

                if status == "completed":
                    video_url = data.get("data", {}).get("video_url", "")
                    if video_url:
                        return download_video(video_url, output_path)
                    break
                elif status == "failed":
                    rprint(f"[red]✗ HeyGen render failed[/red]")
                    return False
            except Exception as e:
                print(f"  Polling error: {e} — retrying...")

    rprint(f"[yellow]⚠ Render timeout after {POLL_TIMEOUT//60} minutes[/yellow]")
    rprint(f"[dim]  Check status manually: make video-status --job {job_id}[/dim]")
    return False


# ── HyperFrames API ───────────────────────────────────────────────────────────
def hyperframes_request(method: str, endpoint: str, payload: dict = None) -> dict:
    """Make a HyperFrames API request."""
    import requests

    # NOTE: HyperFrames API key reuses ElevenLabs key in some integrations,
    # but check hyperframes.ai for their current auth method.
    headers = {
        "Authorization": f"Bearer {ELEVENLABS_API_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{HYPERFRAMES_BASE_URL}/{endpoint.lstrip('/')}"

    try:
        resp = requests.request(
            method.upper(), url,
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        rprint(f"[red]✗ HyperFrames API error {resp.status_code}: {resp.text[:300]}[/red]")
        raise
    except requests.exceptions.RequestException as e:
        rprint(f"[red]✗ HyperFrames connection error: {e}[/red]")
        raise


def submit_hyperframes_short(
    audio_path: Path,
    script_text: str,
    title: str,
    dry_run: bool = False,
) -> str:
    """
    Submit a HyperFrames animated Short generation job.
    Returns job_id.
    """
    file_size_mb = audio_path.stat().st_size / 1024 / 1024

    rprint(f"\n[bold]HyperFrames Short render[/bold]")
    rprint(f"  Audio:  {audio_path.name} ({file_size_mb:.1f} MB)")
    rprint(f"  Format: {SHORTS_WIDTH}x{SHORTS_HEIGHT} (vertical)")

    if dry_run:
        rprint("[dim][DRY RUN] Would submit HyperFrames job — skipping API call[/dim]")
        return "dry_run_job_id"

    # HyperFrames expects the script for visual keyword extraction
    payload = {
        "title":        title[:80],
        "script":       script_text[:2000],
        "audio_url":    "",         # HyperFrames may need hosted audio — see docs
        "dimensions": {
            "width":  SHORTS_WIDTH,
            "height": SHORTS_HEIGHT,
        },
        "style": "professional",    # professional | dynamic | minimal
        "topic": "real_estate",     # helps their visual matching
    }

    # NOTE: HyperFrames may require audio to be hosted (like HeyGen).
    # If local upload is not supported, audio needs to be uploaded to a
    # temporary host first. Check hyperframes.ai/docs for current flow.
    rprint("[yellow]⚠ HyperFrames integration note:[/yellow]")
    rprint("[dim]  Verify audio hosting requirements at hyperframes.ai/docs[/dim]")
    rprint("[dim]  API endpoint and auth may differ from this stub[/dim]")

    try:
        data = hyperframes_request("POST", "/generate", payload)
        job_id = data.get("job_id") or data.get("id", "")
        if not job_id:
            rprint(f"[yellow]⚠ No job ID in HyperFrames response: {data}[/yellow]")
            return ""
        rprint(f"[green]✓ HyperFrames job submitted: {job_id}[/green]")
        return job_id
    except Exception as e:
        rprint(f"[red]✗ HyperFrames submission failed: {e}[/red]")
        rprint("[dim]  HyperFrames is in active development — check docs for latest API[/dim]")
        return ""


def poll_hyperframes_status(job_id: str, output_path: Path) -> bool:
    """Poll HyperFrames until the video is ready, then download it."""
    import requests

    rprint(f"\n[dim]Polling HyperFrames render status (job: {job_id})...[/dim]")
    start = time.time()

    while time.time() - start < POLL_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        try:
            data = hyperframes_request("GET", f"/status/{job_id}")
            status = data.get("status", "")
            elapsed = int(time.time() - start)
            rprint(f"[dim]  [{elapsed}s] {status}[/dim]")

            if status in ("completed", "done", "ready"):
                video_url = data.get("video_url") or data.get("output_url", "")
                if video_url:
                    return download_video(video_url, output_path)
                break
            elif status in ("failed", "error"):
                rprint(f"[red]✗ HyperFrames render failed: {data.get('error','')}[/red]")
                return False

        except Exception as e:
            rprint(f"[dim]  Polling error: {e} — retrying...[/dim]")

    rprint(f"[yellow]⚠ Render timeout[/yellow]")
    return False


# ── Shared utilities ──────────────────────────────────────────────────────────
def download_video(url: str, output_path: Path) -> bool:
    """Download a rendered video from a URL to output_path."""
    import requests

    rprint(f"\n[dim]Downloading video...[/dim]")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        size_mb = output_path.stat().st_size / 1024 / 1024
        rprint(f"[green]✓ Video saved: {output_path.name} ({size_mb:.1f} MB)[/green]")
        return True

    except Exception as e:
        rprint(f"[red]✗ Download failed: {e}[/red]")
        return False


def load_short_script(audio_path: Path) -> str:
    """
    Try to find and load the matching Short script for an audio file.
    Looks for a script file with a matching slug in SCRIPTS_DIR.
    """
    slug = re.sub(r"-short\.mp3$", "", audio_path.name)
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug)  # strip date prefix

    matches = list(Path(runtime.SCRIPTS_DIR).glob(f"*{slug}*-script.md"))
    if not matches:
        return ""

    script_file = sorted(matches)[-1]
    text = script_file.read_text(encoding="utf-8")

    short_match = re.search(
        r"## Short script.*?\n(.+?)(?=\n---\n## |\Z)",
        text, re.DOTALL
    )
    if short_match:
        raw = short_match.group(1)
        # Strip section markers
        raw = re.sub(r"\[HOOK\]|\[BODY\]|\[CTA\]", "", raw)
        return raw.strip()
    return ""


# ── Audio file selection ──────────────────────────────────────────────────────
def pick_audio_files(mode: str) -> list[Path]:
    """
    Let user pick audio files from AUDIO_DIR.
    mode: 'longform' | 'short' | 'both' | 'interactive'
    """
    audio_dir = Path(runtime.AUDIO_DIR)
    if not audio_dir.exists():
        rprint(f"[red]✗ Audio directory not found: {runtime.AUDIO_DIR}[/red]")
        rprint("[dim]  Run generate_voice.py first: make generate-voice[/dim]")
        sys.exit(1)

    all_files = sorted(audio_dir.glob("*.mp3"), reverse=True)
    if not all_files:
        rprint("[red]✗ No .mp3 files found in audio directory[/red]")
        rprint("[dim]  Run generate_voice.py first: make generate-voice[/dim]")
        sys.exit(1)

    longform_files = [f for f in all_files if "longform" in f.name]
    short_files    = [f for f in all_files if "short" in f.name]

    selected = []

    if mode == "longform" and longform_files:
        selected.append(longform_files[0])
    elif mode == "short" and short_files:
        selected.append(short_files[0])
    elif mode == "both":
        if longform_files: selected.append(longform_files[0])
        if short_files:    selected.append(short_files[0])
    else:
        # Interactive
        rprint(f"\n[bold]Available audio files:[/bold]")
        for i, f in enumerate(all_files[:10], 1):
            size_mb = f.stat().st_size / 1024 / 1024
            rprint(f"  [cyan]{i}.[/cyan] {f.name} ({size_mb:.1f} MB)")
        rprint("")
        try:
            raw = input("Pick number(s) comma-separated: ").strip()
            indices = [int(x.strip()) - 1 for x in raw.split(",")]
            selected = [all_files[i] for i in indices]
        except (ValueError, IndexError):
            rprint("[red]✗ Invalid selection[/red]")
            sys.exit(1)

    return selected


def get_latest_audio(mode: str) -> list[Path]:
    """Auto-select most recent audio files."""
    audio_dir = Path(runtime.AUDIO_DIR)
    if not audio_dir.exists():
        rprint(f"[red]✗ Audio directory not found: {runtime.AUDIO_DIR}[/red]")
        sys.exit(1)

    all_files      = sorted(audio_dir.glob("*.mp3"), reverse=True)
    longform_files = [f for f in all_files if "longform" in f.name]
    short_files    = [f for f in all_files if "short"    in f.name]

    selected = []
    if mode in ("longform", "both") and longform_files:
        selected.append(longform_files[0])
        rprint(f"[dim]Long-form: {longform_files[0].name}[/dim]")
    if mode in ("short", "both") and short_files:
        selected.append(short_files[0])
        rprint(f"[dim]Short:     {short_files[0].name}[/dim]")

    if not selected:
        rprint(f"[yellow]⚠ No matching audio files found for mode: {mode}[/yellow]")
        sys.exit(1)

    return selected


# ── Render log ────────────────────────────────────────────────────────────────
def append_render_log(entries: list[dict]):
    """Append render job details to render-log.md for status tracking."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"\n## {timestamp}\n"]

    for e in entries:
        status  = e.get("status", "submitted")
        job_id  = e.get("job_id", "—")
        service = e.get("service", "—")
        output  = e.get("output", "—")
        dry     = " [DRY RUN]" if e.get("dry_run") else ""
        lines.append(f"- **{service}** | job: `{job_id}` | status: {status} | output: {output}{dry}")

    lines.append("")
    try:
        RENDER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(RENDER_LOG, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        rprint(f"[yellow]⚠ Could not write render log: {e}[/yellow]")


# ── Status check ──────────────────────────────────────────────────────────────
def check_job_status(job_id: str, service: str):
    """Check and print the status of a pending render job."""
    rprint(f"\n[bold]Checking job: {job_id} ({service})[/bold]")

    if service == "heygen":
        try:
            data   = heygen_request("GET", f"/v1/video_status.get?video_id={job_id}")
            status = data.get("data", {}).get("status", "unknown")
            url    = data.get("data", {}).get("video_url", "")
            rprint(f"  Status: [bold]{status}[/bold]")
            if url:
                rprint(f"  URL: {url}")
                rprint(f"\n[dim]To download: python3 scripts/generate_video.py --download {url}[/dim]")
        except Exception as e:
            rprint(f"[red]✗ Status check failed: {e}[/red]")
    else:
        rprint("[yellow]⚠ Status check for HyperFrames not yet implemented[/yellow]")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generate videos via HeyGen (long-form) and HyperFrames (Shorts)."
    )
    parser.add_argument("--latest",   action="store_true", help="Auto-pick latest audio files")
    parser.add_argument("--longform", type=str,            help="Path to long-form .mp3 file")
    parser.add_argument("--short",    type=str,            help="Path to Short .mp3 file")
    parser.add_argument("--both",     action="store_true", help="Generate both long-form and Short")
    parser.add_argument("--auto",     action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--dry-run",  action="store_true", help="Preview without calling APIs")
    parser.add_argument("--status",   type=str,            help="Check render status by job ID")
    parser.add_argument("--service",  type=str,            default="heygen",
                        help="Service for --status check (heygen|hyperframes)")
    parser.add_argument("--no-wait",  action="store_true",
                        help="Submit job and exit without polling for completion")
    args = parser.parse_args()

    # ── Status check mode ──
    if args.status:
        check_job_status(args.status, args.service)
        sys.exit(0)

    # ── Validate ──
    if not runtime.VIDEO_DIR:
        print("✗ VIDEO_DIR not set. Check your .env file.")
        sys.exit(1)

    rpanel(
        "[bold green]Video Generator[/bold green]\n"
        "[dim]HeyGen (long-form avatar) · HyperFrames (Shorts)[/dim]",
        width=52,
    )

    # ── Resolve avatar ──
    avatar_id, avatar_label = resolve_avatar_id()
    rprint(f"\n[dim]Avatar: {avatar_label}[/dim]")

    # ── Determine mode ──
    if args.both:
        mode = "both"
    elif args.longform or (args.latest and not args.short):
        mode = "longform"
    elif args.short:
        mode = "short"
    else:
        rprint("\nWhat do you want to generate?")
        rprint("  [cyan]1.[/cyan] Long-form video (HeyGen avatar)")
        rprint("  [cyan]2.[/cyan] Short video (HyperFrames animated)")
        rprint("  [cyan]3.[/cyan] Both")
        rprint("")
        choice = input("Choice (1/2/3): ").strip()
        mode = {"1": "longform", "2": "short", "3": "both"}.get(choice, "longform")

    # ── Collect audio files ──
    audio_files = []

    if args.longform:
        audio_files.append(("longform", Path(args.longform)))
    elif args.short and not args.both:
        audio_files.append(("short", Path(args.short)))
    elif args.latest:
        for f in get_latest_audio(mode):
            ftype = "short" if "short" in f.name else "longform"
            audio_files.append((ftype, f))
    else:
        for f in pick_audio_files(mode):
            ftype = "short" if "short" in f.name else "longform"
            audio_files.append((ftype, f))

    if not audio_files:
        rprint("[red]✗ No audio files selected.[/red]")
        sys.exit(1)

    # ── Confirm ──
    rrule("Render plan")
    for ftype, fpath in audio_files:
        service = "HeyGen" if ftype == "longform" else "HyperFrames"
        size_mb = fpath.stat().st_size / 1024 / 1024 if fpath.exists() else 0
        rprint(f"  [cyan]{ftype:10}[/cyan] → {service} | {fpath.name} ({size_mb:.1f} MB)")

    rprint("")
    if not args.auto and not args.dry_run:
        confirm = input("Proceed with render? (y/n): ").strip().lower()
        if confirm != "y":
            rprint("[yellow]Cancelled.[/yellow]")
            sys.exit(0)

    # ── Build date/slug for output filenames ──
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_entries = []
    results = []

    # ── Process each audio file ──
    for ftype, audio_path in audio_files:

        if not audio_path.exists():
            rprint(f"[red]✗ Audio file not found: {audio_path}[/red]")
            continue

        # Build slug from audio filename
        slug = re.sub(r"-(longform|short)\.mp3$", "", audio_path.name)
        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug)
        slug = re.sub(r"[^a-z0-9]+", "-", slug.lower())[:40].strip("-")

        title = slug.replace("-", " ").title()

        # ── Long-form: HeyGen ──
        if ftype == "longform":
            out_path = Path(runtime.LONGFORM_DIR) / f"{date_str}-{slug}-longform.mp4"

            job_id = submit_heygen_video(
                audio_path, avatar_id, title, args.dry_run
            )

            log_entries.append({
                "service": "HeyGen",
                "job_id":  job_id,
                "status":  "submitted",
                "output":  str(out_path),
                "dry_run": args.dry_run,
            })

            if not args.dry_run and not args.no_wait and job_id != "dry_run_job_id":
                success = poll_heygen_status(job_id, out_path)
                log_entries[-1]["status"] = "completed" if success else "failed"
                results.append({"type": "longform", "success": success, "path": str(out_path)})
            elif args.no_wait:
                rprint(f"\n[dim]Job submitted. Check status with:[/dim]")
                rprint(f"[dim]  python3 scripts/generate_video.py --status {job_id} --service heygen[/dim]")
                results.append({"type": "longform", "success": None, "job_id": job_id})

        # ── Short: HyperFrames ──
        elif ftype == "short":
            out_path   = Path(runtime.SHORTS_DIR) / f"{date_str}-{slug}-short.mp4"
            short_text = load_short_script(audio_path)

            if not short_text:
                rprint("[yellow]⚠ Could not find matching Short script — HyperFrames will use audio only[/yellow]")

            job_id = submit_hyperframes_short(
                audio_path, short_text, title, args.dry_run
            )

            log_entries.append({
                "service": "HyperFrames",
                "job_id":  job_id,
                "status":  "submitted",
                "output":  str(out_path),
                "dry_run": args.dry_run,
            })

            if not args.dry_run and not args.no_wait and job_id:
                success = poll_hyperframes_status(job_id, out_path)
                log_entries[-1]["status"] = "completed" if success else "failed"
                results.append({"type": "short", "success": success, "path": str(out_path)})
            elif args.no_wait and job_id:
                rprint(f"\n[dim]Job submitted. Check status with:[/dim]")
                rprint(f"[dim]  python3 scripts/generate_video.py --status {job_id} --service hyperframes[/dim]")
                results.append({"type": "short", "success": None, "job_id": job_id})

    # ── Log ──
    if log_entries:
        append_render_log(log_entries)
        rprint(f"\n[dim]✓ Render log updated: {RENDER_LOG}[/dim]")

    # ── Summary ──
    if results:
        rrule("Results")
        for r in results:
            if r["success"] is True:
                rprint(f"  [green]✓[/green] {r['type']:10} → {r.get('path','')}")
            elif r["success"] is False:
                rprint(f"  [red]✗[/red] {r['type']:10} → render failed")
            else:
                rprint(f"  [yellow]⏳[/yellow] {r['type']:10} → job {r.get('job_id','')} pending")

        completed = [r for r in results if r.get("success")]
        if completed:
            rprint(f"\n[dim]Videos saved to OneDrive.[/dim]")
            rprint(f"[dim]Next step: upload to Postiz → make schedule[/dim]")

    if args.dry_run:
        rprint("\n[yellow]⚠ Dry run — no API calls were made.[/yellow]")


if __name__ == "__main__":
    main()
