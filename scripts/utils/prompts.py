"""Compose Claude system prompts from scripts/config/prompts.toml.

Each pipeline script's system prompt is a persona plus task-specific rules,
but several pieces — channel description, audience, tone, banned phrases —
are identical across scripts (and mirror docs/ai-instructions/identity-voice.md).
Composing from one config file keeps that voice consistent and lets it be
corrected in one place instead of four.
"""

from scripts.utils.config import load


def build_system_prompt(name: str, channel_name: str) -> str:
    """Build the system prompt for prompts.toml section ``name``."""
    prompts = load("prompts")
    shared = prompts["shared"]
    cfg = prompts[name]
    include = cfg.get("include", [])

    parts = [f"You are {cfg['persona']} for {channel_name}, {shared['channel_description']}."]
    if cfg.get("persona_note"):
        parts.append(cfg["persona_note"])

    if "audience" in include:
        parts.append(f"Audience: {shared['audience']}")
    if cfg.get("audience_notes"):
        parts.append(cfg["audience_notes"])
    if "tone" in include:
        parts.append(f"Tone: {shared['tone']}")

    if cfg.get("task"):
        parts.append(cfg["task"])

    if cfg.get("platform_rules"):
        parts.append("Platform-specific rules:\n" + "\n".join(f"- {r}" for r in cfg["platform_rules"]))

    if cfg.get("style_rules"):
        parts.append("Writing rules:\n" + "\n".join(f"- {r}" for r in cfg["style_rules"]))

    if "banned_phrases" in include:
        phrases = ", ".join(f'"{p}"' for p in shared["banned_phrases"])
        parts.append(f"Never use: {phrases}")

    if cfg.get("disclaimer"):
        parts.append(f'Always include this disclaimer variant somewhere natural in the script:\n"{cfg["disclaimer"]}"')

    if cfg.get("notes"):
        parts.append("\n".join(cfg["notes"]))

    if cfg.get("output_framing"):
        parts.append(cfg["output_framing"])

    return "\n\n".join(parts)
