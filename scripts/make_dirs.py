import os
import sys
from pathlib import Path

from scripts.utils.path_utils import create_directories, resolve

# debug: doppler run --project video_production --config dev -- python3 scripts/make_dirs.py

def run() -> None:
    base_dir: str = "BASE_CONTENT_DIR"

    directory_keys: list[str] = [
        "SCRIPTS_DIR",
        "REPURPOSED_DIR",
        "ANALYTICS_DIR",
        "IDEAS_DIR",
    ]

    touch_keys: dict[str, str] = {
        "IDEAS_DIR": "backlog.md",
    }

    try:
        create_directories(base_dir, directory_keys, touch_keys)
    except ValueError as exc:
        sys.exit(f"✗ {exc} Run: make env-check")

    base_path: str = resolve(os.getenv(base_dir, ""))
    print(f"✓ Content directories created at {base_path}")


if __name__ == "__main__":
    run()