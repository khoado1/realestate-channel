#!/usr/bin/env python3
"""
analytics.py — Pipeline A: YouTube Analytics & Feedback Loop
=============================================================
Pulls YouTube channel and video analytics, generates insights,
and feeds performance patterns back into the content pipeline.

Usage:
    python3 scripts/analytics.py                        # interactive mode
    python3 scripts/analytics.py --weekly               # weekly digest (last 7 days)
    python3 scripts/analytics.py --video <video_id>     # single video deep dive
    python3 scripts/analytics.py --weekly --no-save     # terminal only

Requires:
    - YOUTUBE_API_KEY in .env (YouTube Data API v3)
    - YOUTUBE_CHANNEL_ID in .env

Output:
    - Terminal: rich-formatted analytics summary
    - File: $ANALYTICS_DIR/YYYY-MM/YYYY-MM-DD-[mode]-report.md

Feedback loop:
    - Flags videos with >50% drop-off in first 30 seconds
    - Flags high-retention videos (>60% avg view duration)
    - Appends performance patterns to ideas/backlog.md as content signals
"""

import sys
import json
import argparse
from datetime import datetime, timedelta, date
from pathlib import Path

from scripts.providers.base import ProviderError
from scripts.providers.calls import call_ai, youtube_get
from scripts.runtime import RuntimeConfig

runtime = RuntimeConfig(
    paths=["ANALYTICS_DIR", "IDEAS_DIR"],
    env=["YOUTUBE_API_KEY", ("YOUTUBE_CHANNEL_ID", "CHANNEL_ID"), "CHANNEL_NAME"],
)

# ── Thresholds for flagging ───────────────────────────────────────────────────
RETENTION_FLAG_LOW  = 0.50   # flag if avg view duration < 50% (hook problem)
RETENTION_FLAG_HIGH = 0.60   # flag as winner if avg view duration > 60%
EARLY_DROPOFF_SECS  = 30     # seconds — flag hook if drop-off spikes here

from scripts.utils.console import RICH, Table, console, rpanel, rprint, rrule


# ── Anthropic API — insights generation ──────────────────────────────────────
def call_claude(prompt: str, max_tokens: int = 1000) -> str:
    # Analytics degrades gracefully — a failed insight call must not break the report.
    return call_ai("analytics", prompt, channel_name=runtime.CHANNEL_NAME, max_tokens=max_tokens, on_error="placeholder")


# ── YouTube Data API helpers ──────────────────────────────────────────────────
def yt_request(endpoint: str, params: dict) -> dict:
    """Make a YouTube Data API v3 request."""
    if not runtime.YOUTUBE_API_KEY:
        rprint("[red]✗ YOUTUBE_API_KEY not set in .env[/red]")
        sys.exit(1)

    try:
        return youtube_get(endpoint, params, api_key=runtime.YOUTUBE_API_KEY, timeout=15)
    except ProviderError as e:
        rprint(f"[red]✗ YouTube API error: {e}[/red]")
        return {}


def yt_analytics_request(params: dict) -> dict:
    """Make a YouTube Analytics API request (requires OAuth — see note)."""
    # NOTE: YouTube Analytics API requires OAuth 2.0, not just an API key.
    # This function is a stub — full OAuth flow documented in README.
    # For now, we derive approximate analytics from the Data API where possible.
    rprint("[yellow]⚠ YouTube Analytics API requires OAuth setup.[/yellow]")
    rprint("[dim]  See: https://developers.google.com/youtube/analytics/getting_started[/dim]")
    return {}


# ── Data fetchers ─────────────────────────────────────────────────────────────
def fetch_channel_stats() -> dict:
    """Fetch channel-level statistics."""
    if not runtime.YOUTUBE_CHANNEL_ID:
        rprint("[yellow]⚠ YOUTUBE_CHANNEL_ID not set — using channel search[/yellow]")
        return {}

    data = yt_request("channels", {
        "part": "statistics,snippet,brandingSettings",
        "id": runtime.YOUTUBE_CHANNEL_ID,
    })

    items = data.get("items", [])
    if not items:
        return {}

    item  = items[0]
    stats = item.get("statistics", {})
    return {
        "channel_name":   item.get("snippet", {}).get("title", runtime.CHANNEL_NAME),
        "subscribers":    int(stats.get("subscriberCount", 0)),
        "total_views":    int(stats.get("viewCount", 0)),
        "total_videos":   int(stats.get("videoCount", 0)),
        "fetched_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def fetch_recent_videos(max_results: int = 20) -> list[dict]:
    """Fetch recent uploads with stats."""
    if not runtime.YOUTUBE_CHANNEL_ID:
        return []

    # Get uploads playlist ID
    channel_data = yt_request("channels", {
        "part": "contentDetails",
        "id": runtime.YOUTUBE_CHANNEL_ID,
    })
    items = channel_data.get("items", [])
    if not items:
        return []

    uploads_playlist = (
        items[0]
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads", "")
    )
    if not uploads_playlist:
        return []

    # Get recent video IDs from uploads playlist
    playlist_data = yt_request("playlistItems", {
        "part": "snippet,contentDetails",
        "playlistId": uploads_playlist,
        "maxResults": max_results,
    })

    video_ids = [
        item["contentDetails"]["videoId"]
        for item in playlist_data.get("items", [])
    ]
    if not video_ids:
        return []

    # Fetch stats for all videos in one request
    stats_data = yt_request("videos", {
        "part": "statistics,snippet,contentDetails",
        "id": ",".join(video_ids),
    })

    videos = []
    for item in stats_data.get("items", []):
        snippet    = item.get("snippet", {})
        stats      = item.get("statistics", {})
        duration   = item.get("contentDetails", {}).get("duration", "PT0S")
        published  = snippet.get("publishedAt", "")[:10]

        # Parse ISO 8601 duration to seconds
        duration_secs = parse_duration(duration)

        views     = int(stats.get("viewCount", 0))
        likes     = int(stats.get("likeCount", 0))
        comments  = int(stats.get("commentCount", 0))

        videos.append({
            "video_id":       item["id"],
            "title":          snippet.get("title", ""),
            "published":      published,
            "duration_secs":  duration_secs,
            "views":          views,
            "likes":          likes,
            "comments":       comments,
            "like_rate":      round(likes / views * 100, 2) if views > 0 else 0,
            "comment_rate":   round(comments / views * 100, 2) if views > 0 else 0,
            "url":            f"https://youtu.be/{item['id']}",
        })

    return sorted(videos, key=lambda x: x["published"], reverse=True)


def fetch_video_detail(video_id: str) -> dict:
    """Fetch detailed stats for a single video."""
    data = yt_request("videos", {
        "part": "statistics,snippet,contentDetails",
        "id": video_id,
    })
    items = data.get("items", [])
    if not items:
        rprint(f"[red]✗ Video not found: {video_id}[/red]")
        sys.exit(1)

    item     = items[0]
    snippet  = item.get("snippet", {})
    stats    = item.get("statistics", {})
    duration = item.get("contentDetails", {}).get("duration", "PT0S")

    views    = int(stats.get("viewCount", 0))
    likes    = int(stats.get("likeCount", 0))
    comments = int(stats.get("commentCount", 0))

    return {
        "video_id":      video_id,
        "title":         snippet.get("title", ""),
        "description":   snippet.get("description", "")[:500],
        "published":     snippet.get("publishedAt", "")[:10],
        "tags":          snippet.get("tags", []),
        "duration_secs": parse_duration(duration),
        "views":         views,
        "likes":         likes,
        "comments":      comments,
        "like_rate":     round(likes / views * 100, 2) if views > 0 else 0,
        "comment_rate":  round(comments / views * 100, 2) if views > 0 else 0,
        "url":           f"https://youtu.be/{video_id}",
    }


def parse_duration(iso_duration: str) -> int:
    """Parse ISO 8601 duration (PT4M13S) to seconds."""
    import re
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    match = re.match(pattern, iso_duration)
    if not match:
        return 0
    hours   = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def fetch_search_terms() -> list[dict]:
    """
    Fetch top search terms that brought viewers.
    NOTE: Requires YouTube Analytics API with OAuth.
    Returns placeholder with instructions until OAuth is set up.
    """
    return [{"term": "OAuth required", "impressions": 0,
             "note": "Set up YouTube Analytics OAuth to unlock search term data"}]


# ── Analysis ──────────────────────────────────────────────────────────────────
def analyze_videos(videos: list[dict]) -> dict:
    """Run analysis across a list of videos. Returns flags and patterns."""
    if not videos:
        return {}

    total_views = sum(v["views"] for v in videos)
    avg_views   = total_views / len(videos) if videos else 0

    # Top performers
    by_views    = sorted(videos, key=lambda x: x["views"], reverse=True)
    by_likes    = sorted(videos, key=lambda x: x["like_rate"], reverse=True)
    by_comments = sorted(videos, key=lambda x: x["comment_rate"], reverse=True)

    # Shorts vs long-form
    shorts    = [v for v in videos if v["duration_secs"] <= 60]
    longform  = [v for v in videos if v["duration_secs"] > 60]

    shorts_avg_views   = sum(v["views"] for v in shorts) / len(shorts) if shorts else 0
    longform_avg_views = sum(v["views"] for v in longform) / len(longform) if longform else 0

    return {
        "total_videos":         len(videos),
        "total_views":          total_views,
        "avg_views":            round(avg_views),
        "top_by_views":         by_views[:3],
        "top_by_engagement":    by_likes[:3],
        "top_by_comments":      by_comments[:3],
        "shorts_count":         len(shorts),
        "longform_count":       len(longform),
        "shorts_avg_views":     round(shorts_avg_views),
        "longform_avg_views":   round(longform_avg_views),
        "below_avg":            [v for v in videos if v["views"] < avg_views * 0.5],
        "above_avg":            [v for v in videos if v["views"] > avg_views * 1.5],
    }


def generate_insights(channel_stats: dict, analysis: dict, videos: list[dict]) -> str:
    """Use Claude to generate actionable insights from the analytics data."""
    prompt = f"""Analyze this YouTube channel performance data and give 3-5 specific,
actionable content insights. Focus on what to do differently, not just observations.

Channel: {channel_stats.get('channel_name', runtime.CHANNEL_NAME)}
Subscribers: {channel_stats.get('subscribers', 'unknown'):,}
Total videos analyzed: {analysis.get('total_videos', 0)}
Average views per video: {analysis.get('avg_views', 0):,}

Top 3 videos by views:
{json.dumps([{{'title': v['title'], 'views': v['views'], 'like_rate': v['like_rate']}} for v in analysis.get('top_by_views', [])], indent=2)}

Top 3 videos by engagement (like rate):
{json.dumps([{{'title': v['title'], 'like_rate': v['like_rate'], 'views': v['views']}} for v in analysis.get('top_by_engagement', [])], indent=2)}

Shorts vs Long-form:
- Shorts ({analysis.get('shorts_count',0)} videos): avg {analysis.get('shorts_avg_views',0):,} views
- Long-form ({analysis.get('longform_count',0)} videos): avg {analysis.get('longform_avg_views',0):,} views

Underperforming videos (below 50% of channel avg):
{json.dumps([{{'title': v['title'], 'views': v['views']}} for v in analysis.get('below_avg', [])[:3]], indent=2)}

Give insights as numbered list. Each insight: observation → why it matters → specific action to take.
Focus on real estate/mortgage content strategy."""

    return call_claude(prompt)


# ── Output ────────────────────────────────────────────────────────────────────
def print_weekly_report(
    channel_stats: dict,
    videos: list[dict],
    analysis: dict,
    insights: str,
):
    """Print weekly digest to terminal."""
    rpanel(
        f"[bold green]Weekly Analytics Report[/bold green]\n"
        f"[dim]{channel_stats.get('channel_name', runtime.CHANNEL_NAME)} · "
        f"{datetime.now().strftime('%Y-%m-%d')}[/dim]",
        width=56,
    )

    # Channel overview
    rrule("Channel Overview")
    rprint(f"  Subscribers: [bold]{channel_stats.get('subscribers', '—'):,}[/bold]")
    rprint(f"  Total views: [bold]{channel_stats.get('total_views', '—'):,}[/bold]")
    rprint(f"  Total videos: [bold]{channel_stats.get('total_videos', '—'):,}[/bold]")

    # Top videos table
    rrule("Top Videos by Views")
    if RICH:
        table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0,1))
        table.add_column("Title",       width=38)
        table.add_column("Views",       width=8,  justify="right")
        table.add_column("Likes %",     width=8,  justify="right")
        table.add_column("Comments %",  width=10, justify="right")
        table.add_column("Published",   width=12)

        for v in analysis.get("top_by_views", []):
            table.add_row(
                v["title"][:37],
                f"{v['views']:,}",
                f"{v['like_rate']}%",
                f"{v['comment_rate']}%",
                v["published"],
            )
        console.print(table)
    else:
        for v in analysis.get("top_by_views", []):
            print(f"  {v['title'][:40]:40} | {v['views']:>8,} views | {v['like_rate']}% likes")

    # Shorts vs long-form
    rrule("Format Comparison")
    rprint(f"  Shorts ({analysis.get('shorts_count',0)} videos):    avg [bold]{analysis.get('shorts_avg_views',0):,}[/bold] views")
    rprint(f"  Long-form ({analysis.get('longform_count',0)} videos): avg [bold]{analysis.get('longform_avg_views',0):,}[/bold] views")

    # Flags
    below_avg = analysis.get("below_avg", [])
    above_avg = analysis.get("above_avg", [])

    if below_avg:
        rrule("⚠ Hook Review Needed (below 50% channel avg)")
        for v in below_avg[:3]:
            rprint(f"  [yellow]↓[/yellow] {v['title'][:50]} — {v['views']:,} views")

    if above_avg:
        rrule("✓ High Performers (above 150% channel avg)")
        for v in above_avg[:3]:
            rprint(f"  [green]↑[/green] {v['title'][:50]} — {v['views']:,} views")

    # Insights
    rrule("AI Insights")
    rprint(insights)


def print_video_report(video: dict, insights: str):
    """Print single video deep dive to terminal."""
    rpanel(
        f"[bold green]Video Deep Dive[/bold green]\n"
        f"[dim]{video['title'][:50]}[/dim]",
        width=56,
    )

    rrule("Stats")
    rprint(f"  Views:        [bold]{video['views']:,}[/bold]")
    rprint(f"  Likes:        [bold]{video['likes']:,}[/bold] ({video['like_rate']}%)")
    rprint(f"  Comments:     [bold]{video['comments']:,}[/bold] ({video['comment_rate']}%)")
    rprint(f"  Duration:     [bold]{video['duration_secs']//60}m {video['duration_secs']%60}s[/bold]")
    rprint(f"  Published:    [bold]{video['published']}[/bold]")
    rprint(f"  URL:          [dim]{video['url']}[/dim]")

    if video.get("tags"):
        rrule("Tags")
        rprint(f"  {', '.join(video['tags'][:10])}")

    rrule("AI Insights")
    rprint(insights)


# ── Save report ───────────────────────────────────────────────────────────────
def save_report(
    mode: str,
    channel_stats: dict,
    videos: list[dict],
    analysis: dict,
    insights: str,
    video_detail: dict = None,
) -> str:
    """Save analytics report to $ANALYTICS_DIR/YYYY-MM/."""
    date_str  = datetime.now().strftime("%Y-%m-%d")
    month_str = datetime.now().strftime("%Y-%m")
    filename  = f"{date_str}-{mode}-report.md"
    out_dir   = Path(runtime.ANALYTICS_DIR) / month_str
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path  = out_dir / filename

    lines = [
        f"# Analytics Report — {mode.title()} — {date_str}",
        f"**Channel:** {channel_stats.get('channel_name', runtime.CHANNEL_NAME)}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## Channel stats",
        f"- Subscribers: {channel_stats.get('subscribers', '—'):,}",
        f"- Total views: {channel_stats.get('total_views', '—'):,}",
        f"- Total videos: {channel_stats.get('total_videos', '—'):,}",
        "",
    ]

    if mode == "weekly" and analysis:
        lines += [
            "## Performance summary",
            f"- Videos analyzed: {analysis.get('total_videos', 0)}",
            f"- Average views: {analysis.get('avg_views', 0):,}",
            f"- Shorts avg views: {analysis.get('shorts_avg_views', 0):,}",
            f"- Long-form avg views: {analysis.get('longform_avg_views', 0):,}",
            "",
            "## Top videos by views",
        ]
        for v in analysis.get("top_by_views", []):
            lines.append(f"1. [{v['title']}]({v['url']}) — {v['views']:,} views | {v['like_rate']}% likes")
        lines.append("")

        below = analysis.get("below_avg", [])
        if below:
            lines.append("## ⚠ Hook review needed")
            for v in below[:3]:
                lines.append(f"- [{v['title']}]({v['url']}) — {v['views']:,} views")
            lines.append("")

        above = analysis.get("above_avg", [])
        if above:
            lines.append("## ✓ High performers — replicate these")
            for v in above[:3]:
                lines.append(f"- [{v['title']}]({v['url']}) — {v['views']:,} views")
            lines.append("")

    if mode == "video" and video_detail:
        lines += [
            "## Video stats",
            f"- Title: {video_detail['title']}",
            f"- URL: {video_detail['url']}",
            f"- Views: {video_detail['views']:,}",
            f"- Likes: {video_detail['likes']:,} ({video_detail['like_rate']}%)",
            f"- Comments: {video_detail['comments']:,} ({video_detail['comment_rate']}%)",
            f"- Duration: {video_detail['duration_secs']//60}m {video_detail['duration_secs']%60}s",
            f"- Published: {video_detail['published']}",
            "",
        ]

    lines += [
        "## AI insights",
        "",
        insights,
        "",
        "---",
        "",
        "## Raw data",
        "```json",
        json.dumps(videos[:10] if videos else [], indent=2),
        "```",
    ]

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)


def append_feedback_to_backlog(analysis: dict):
    """
    Append performance signals to ideas/backlog.md as content feedback.
    This closes the feedback loop — analytics inform future research.
    """
    backlog = Path(runtime.IDEAS_DIR) / "backlog.md"
    date_str = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"\n## {date_str} — performance signals\n",
        "_Automatically appended by analytics.py — use these to inform next research run_\n",
    ]

    top = analysis.get("top_by_views", [])
    if top:
        lines.append("**Replicate these patterns:**")
        for v in top[:3]:
            lines.append(f"- [ ] Similar to: {v['title']}")
        lines.append("")

    below = analysis.get("below_avg", [])
    if below:
        lines.append("**Hook review — consider reworking or retiring:**")
        for v in below[:3]:
            lines.append(f"- {v['title']} ({v['views']:,} views)")
        lines.append("")

    try:
        backlog.parent.mkdir(parents=True, exist_ok=True)
        with open(backlog, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))
        rprint(f"[green]✓ Performance signals appended to backlog.md[/green]")
    except Exception as e:
        rprint(f"[yellow]⚠ Could not update backlog: {e}[/yellow]")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Pull YouTube analytics and generate performance insights."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--weekly",  action="store_true", help="Weekly digest (last 20 videos)")
    group.add_argument("--video",   type=str,            help="Single video deep dive (video ID or URL)")
    parser.add_argument("--no-save",    action="store_true", help="Terminal output only")
    parser.add_argument("--no-backlog", action="store_true", help="Skip appending to backlog.md")
    args = parser.parse_args()

    # ── Validate ──
    if not runtime.CONTENT_DIR:
        print("✗ BASE_CONTENT_DIR not set. Check your .env file.")
        sys.exit(1)
    if not runtime.YOUTUBE_API_KEY:
        print("✗ YOUTUBE_API_KEY not set. Check your .env file.")
        sys.exit(1)
    if not runtime.YOUTUBE_CHANNEL_ID:
        print("✗ YOUTUBE_CHANNEL_ID not set. Add it to your .env file.")
        print("  Find it at: https://www.youtube.com/account_advanced")
        sys.exit(1)

    rpanel(
        "[bold green]YouTube Analytics[/bold green]\n"
        "[dim]Views · Retention · Traffic · Subscribers[/dim]",
        width=50,
    )

    # ── Determine mode ──
    if args.video:
        mode = "video"
    elif args.weekly:
        mode = "weekly"
    else:
        rprint("\nChoose mode:")
        rprint("  [cyan]1.[/cyan] Weekly digest")
        rprint("  [cyan]2.[/cyan] Single video deep dive")
        rprint("")
        choice = input("Choice (1/2): ").strip()
        mode = "video" if choice == "2" else "weekly"

    # ── Fetch channel stats (both modes) ──
    rprint("\n[dim]Fetching channel stats...[/dim]")
    channel_stats = fetch_channel_stats()

    # ── Weekly mode ──
    if mode == "weekly":
        rprint("[dim]Fetching recent videos...[/dim]")
        videos = fetch_recent_videos(max_results=20)

        if not videos:
            rprint("[yellow]⚠ No videos found. Check YOUTUBE_CHANNEL_ID in .env[/yellow]")
            sys.exit(1)

        rprint(f"[dim]Analyzing {len(videos)} videos...[/dim]")
        analysis = analyze_videos(videos)

        rprint("[dim]Generating insights...[/dim]\n")
        insights = generate_insights(channel_stats, analysis, videos)

        print_weekly_report(channel_stats, videos, analysis, insights)

        if not args.no_save:
            path = save_report("weekly", channel_stats, videos, analysis, insights)
            rprint(f"\n[green]✓ Saved:[/green] {path}")

        if not args.no_backlog:
            append_feedback_to_backlog(analysis)

    # ── Single video mode ──
    elif mode == "video":
        video_input = args.video if args.video else input("\nEnter video ID or URL: ").strip()

        # Extract ID from URL if needed
        import re
        match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", video_input)
        video_id = match.group(1) if match else video_input

        rprint(f"\n[dim]Fetching video: {video_id}...[/dim]")
        video = fetch_video_detail(video_id)

        rprint("[dim]Generating insights...[/dim]\n")
        insights_prompt = f"""Analyze this single YouTube video's performance:

Title: {video['title']}
Views: {video['views']:,}
Likes: {video['likes']:,} ({video['like_rate']}% like rate)
Comments: {video['comments']:,} ({video['comment_rate']}% comment rate)
Duration: {video['duration_secs']//60}m {video['duration_secs']%60}s
Published: {video['published']}
Tags: {', '.join(video.get('tags', [])[:10])}

Give 3-5 specific insights about this video's performance:
- What's working (if like/comment rates are strong)
- What's not working (if views are low relative to engagement or vice versa)
- What this suggests about the hook, title, or content format
- One specific recommendation for the next video on a similar topic"""

        insights = call_claude(insights_prompt)

        print_video_report(video, insights)

        if not args.no_save:
            path = save_report("video", channel_stats, [], {}, insights, video)
            rprint(f"\n[green]✓ Saved:[/green] {path}")


if __name__ == "__main__":
    main()
