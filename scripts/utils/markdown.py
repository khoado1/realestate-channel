"""Shared markdown-file helpers."""

import hashlib
from pathlib import Path


def append_once(path: Path, content: str) -> bool:
    """Append content to a markdown file, once per unique content hash.

    Writes an ``<!-- signal:<hash> -->`` marker after the content and skips
    the append if that marker is already present in the file — makes a
    repeated call (retry, accidental rerun) with identical content a no-op
    instead of duplicating the entry, while genuinely new content still
    appends.

    Returns True if the content was appended, False if it was already there.
    """
    key = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    marker = f"<!-- signal:{key} -->"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and marker in path.read_text(encoding="utf-8"):
        return False
    with open(path, "a", encoding="utf-8") as f:
        if not content.endswith("\n"):
            content += "\n"
        f.write(content)
        f.write(f"{marker}\n")
    return True
