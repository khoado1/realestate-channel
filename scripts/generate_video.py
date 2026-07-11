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

import sys
import re
import time
import argparse
from datetime import datetime
from pathlib import Path

from scripts.providers import ProviderError, VideoRequest, get_provider
from scripts.providers import http as provider_http
from scripts.runtime import RuntimeConfig
from scripts.utils.errors import PipelineError

# Render config (avatars, dimensions, endpoints, auth) lives in the video providers.
# Poll interval for render status checks (seconds)
POLL_INTERVAL = 15
POLL_TIMEOUT  = 1800   # 30 minutes max wait

from scripts.utils.console import (
    RICH,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    console,
    rpanel,
    rprint,
    rrule,
)


# ── HeyGen (long-form avatar video) ───────────────────────────────────────────
def submit_heygen_video(audio_path: Path, title: str, dry_run: bool = False) -> str:
    """Submit a HeyGen render job. Returns job_id (or a sentinel on dry run)."""
    provider = get_provider("video", "heygen")
    avatar_id, avatar_label = provider.resolve_avatar()
    file_size_mb = audio_path.stat().st_size / 1024 / 1024

    rprint(f"\n[bold]HeyGen long-form render[/bold]")
    rprint(f"  Avatar:  {avatar_label} ({avatar_id})")
    rprint(f"  Audio:   {audio_path.name} ({file_size_mb:.1f} MB)")
    rprint(f"  Format:  16:9 landscape")

    if dry_run:
        rprint("[dim][DRY RUN] Would submit HeyGen job — skipping API call[/dim]")
        return "dry_run_job_id"

    try:
        rprint("[dim]Uploading audio to HeyGen asset store...[/dim]")
        asset_id = provider.upload_audio(audio_path)
        rprint(f"[green]✓ Audio uploaded: {asset_id}[/green]")
        job_id = provider.submit(
            VideoRequest(audio_path=audio_path, title=title, audio_asset_id=asset_id)
        )
        rprint(f"[green]✓ HeyGen job submitted: {job_id}[/green]")
        return job_id
    except ProviderError as e:
        rprint(f"[red]✗ HeyGen submission failed: {e}[/red]")
        raise PipelineError(f"HeyGen submission failed: {e}") from e


# ── Shared polling ────────────────────────────────────────────────────────────
def poll_and_download(provider, service: str, job_id: str, output_path: Path) -> bool:
    """Poll a video provider until the render finishes, then download it."""
    rprint(f"\n[dim]Polling {service} render status (job: {job_id})...[/dim]")
    start = time.time()

    def _finish(st) -> bool:
        if st.state == "completed" and st.video_url:
            return download_video(st.video_url, output_path)
        if st.state == "failed":
            rprint(f"[red]✗ {service} render failed: {st.error}[/red]")
        return False

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
                    st = provider.status(job_id)
                    progress.update(task, description=f"Rendering... [{st.state}]")
                    if st.state in ("completed", "failed"):
                        progress.stop()
                        return _finish(st)
                except ProviderError as e:
                    progress.update(task, description=f"Polling error: {e} — retrying...")
    else:
        while time.time() - start < POLL_TIMEOUT:
            time.sleep(POLL_INTERVAL)
            try:
                st = provider.status(job_id)
                elapsed = int(time.time() - start)
                print(f"  [{elapsed}s] Status: {st.state}")
                if st.state in ("completed", "failed"):
                    return _finish(st)
            except ProviderError as e:
                print(f"  Polling error: {e} — retrying...")

    rprint(f"[yellow]⚠ Render timeout after {POLL_TIMEOUT//60} minutes[/yellow]")
    rprint(f"[dim]  Check status manually: make video-status --job {job_id}[/dim]")
    return False


# ── HyperFrames (animated Shorts) ─────────────────────────────────────────────
def submit_hyperframes_short(
    audio_path: Path,
    script_text: str,
    title: str,
    dry_run: bool = False,
) -> str:
    """Submit a HyperFrames Short render job. Returns job_id ("" if none)."""
    provider = get_provider("video", "hyperframes")
    file_size_mb = audio_path.stat().st_size / 1024 / 1024

    rprint(f"\n[bold]HyperFrames Short render[/bold]")
    rprint(f"  Audio:  {audio_path.name} ({file_size_mb:.1f} MB)")
    rprint(f"  Format: 9:16 vertical")

    if dry_run:
        rprint("[dim][DRY RUN] Would submit HyperFrames job — skipping API call[/dim]")
        return "dry_run_job_id"

    # NOTE: HyperFrames may require audio to be hosted (like HeyGen).
    rprint("[yellow]⚠ HyperFrames integration note:[/yellow]")
    rprint("[dim]  Verify audio hosting requirements at hyperframes.ai/docs[/dim]")
    rprint("[dim]  API endpoint and auth may differ from this stub[/dim]")

    try:
        job_id = provider.submit(
            VideoRequest(audio_path=audio_path, title=title, script_text=script_text)
        )
        if not job_id:
            rprint("[yellow]⚠ No job ID in HyperFrames response[/yellow]")
            return ""
        rprint(f"[green]✓ HyperFrames job submitted: {job_id}[/green]")
        return job_id
    except ProviderError as e:
        rprint(f"[red]✗ HyperFrames submission failed: {e}[/red]")
        rprint("[dim]  HyperFrames is in active development — check docs for latest API[/dim]")
        return ""


# ── Shared utilities ──────────────────────────────────────────────────────────
def download_video(url: str, output_path: Path) -> bool:
    """Download a rendered video from a URL to output_path."""
    rprint(f"\n[dim]Downloading video...[/dim]")
    try:
        provider_http.stream_to_file("GET", url, output_path, timeout=300, chunk_size=65536)
        size_mb = output_path.stat().st_size / 1024 / 1024
        rprint(f"[green]✓ Video saved: {output_path.name} ({size_mb:.1f} MB)[/green]")
        return True
    except ProviderError as e:
        rprint(f"[red]✗ Download failed: {e}[/red]")
        return False


def load_short_script(audio_path: Path, runtime: RuntimeConfig) -> str:
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
def pick_audio_files(mode: str, runtime: RuntimeConfig) -> list[Path]:
    """
    Let user pick audio files from AUDIO_DIR.
    mode: 'longform' | 'short' | 'both' | 'interactive'
    """
    audio_dir = Path(runtime.AUDIO_DIR)
    if not audio_dir.exists():
        rprint(f"[red]✗ Audio directory not found: {runtime.AUDIO_DIR}[/red]")
        rprint("[dim]  Run generate_voice.py first: make generate-voice[/dim]")
        raise PipelineError(f"audio directory not found: {runtime.AUDIO_DIR}")

    all_files = sorted(audio_dir.glob("*.mp3"), reverse=True)
    if not all_files:
        rprint("[red]✗ No .mp3 files found in audio directory[/red]")
        rprint("[dim]  Run generate_voice.py first: make generate-voice[/dim]")
        raise PipelineError("no .mp3 files found in audio directory")

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
            raise PipelineError("invalid audio file selection")

    return selected


def get_latest_audio(mode: str, runtime: RuntimeConfig) -> list[Path]:
    """Auto-select most recent audio files."""
    audio_dir = Path(runtime.AUDIO_DIR)
    if not audio_dir.exists():
        rprint(f"[red]✗ Audio directory not found: {runtime.AUDIO_DIR}[/red]")
        raise PipelineError(f"audio directory not found: {runtime.AUDIO_DIR}")

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
        raise PipelineError(f"no matching audio files found for mode: {mode}")

    return selected


# ── Render log ────────────────────────────────────────────────────────────────
def render_log_path(runtime: RuntimeConfig) -> Path:
    return Path(runtime.VIDEO_DIR) / "render-log.md" if runtime.VIDEO_DIR else Path("render-log.md")


def append_render_log(entries: list[dict], runtime: RuntimeConfig):
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
    render_log = render_log_path(runtime)
    try:
        render_log.parent.mkdir(parents=True, exist_ok=True)
        with open(render_log, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        rprint(f"[yellow]⚠ Could not write render log: {e}[/yellow]")


# ── Status check ──────────────────────────────────────────────────────────────
def check_job_status(job_id: str, service: str):
    """Check and print the status of a pending render job."""
    rprint(f"\n[bold]Checking job: {job_id} ({service})[/bold]")

    try:
        provider = get_provider("video", service)
    except ProviderError as e:
        rprint(f"[red]✗ {e}[/red]")
        return

    try:
        st = provider.status(job_id)
        rprint(f"  Status: [bold]{st.state}[/bold]")
        if st.error:
            rprint(f"  Error: {st.error}")
        if st.video_url:
            rprint(f"  URL: {st.video_url}")
            rprint(f"\n[dim]To download: python3 scripts/generate_video.py --download {st.video_url}[/dim]")
    except ProviderError as e:
        rprint(f"[red]✗ Status check failed: {e}[/red]")


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

    runtime = RuntimeConfig(
        paths=["SCRIPTS_DIR", "VIDEO_DIR", "AUDIO_DIR", "LONGFORM_DIR", "SHORTS_DIR"],
    )

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
        for f in get_latest_audio(mode, runtime):
            ftype = "short" if "short" in f.name else "longform"
            audio_files.append((ftype, f))
    else:
        for f in pick_audio_files(mode, runtime):
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

            job_id = submit_heygen_video(audio_path, title, args.dry_run)

            log_entries.append({
                "service": "HeyGen",
                "job_id":  job_id,
                "status":  "submitted",
                "output":  str(out_path),
                "dry_run": args.dry_run,
            })

            if not args.dry_run and not args.no_wait and job_id != "dry_run_job_id":
                success = poll_and_download(get_provider("video", "heygen"), "HeyGen", job_id, out_path)
                log_entries[-1]["status"] = "completed" if success else "failed"
                results.append({"type": "longform", "success": success, "path": str(out_path)})
            elif args.no_wait:
                rprint(f"\n[dim]Job submitted. Check status with:[/dim]")
                rprint(f"[dim]  python3 scripts/generate_video.py --status {job_id} --service heygen[/dim]")
                results.append({"type": "longform", "success": None, "job_id": job_id})

        # ── Short: HyperFrames ──
        elif ftype == "short":
            out_path   = Path(runtime.SHORTS_DIR) / f"{date_str}-{slug}-short.mp4"
            short_text = load_short_script(audio_path, runtime)

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
                success = poll_and_download(get_provider("video", "hyperframes"), "HyperFrames", job_id, out_path)
                log_entries[-1]["status"] = "completed" if success else "failed"
                results.append({"type": "short", "success": success, "path": str(out_path)})
            elif args.no_wait and job_id:
                rprint(f"\n[dim]Job submitted. Check status with:[/dim]")
                rprint(f"[dim]  python3 scripts/generate_video.py --status {job_id} --service hyperframes[/dim]")
                results.append({"type": "short", "success": None, "job_id": job_id})

    # ── Log ──
    if log_entries:
        append_render_log(log_entries, runtime)
        rprint(f"\n[dim]✓ Render log updated: {render_log_path(runtime)}[/dim]")

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
    try:
        main()
    except PipelineError:
        sys.exit(1)
