import os
import sys
from pathlib import Path
import re

# debug: doppler run --project video_production --config dev -- python3 scripts/make_dirs.py

def resolve(value: str) -> str:
    if not value:
        return ""
    
    # Convert $(VAR) syntax to $VAR syntax so expandvars() can expand it
    normalized = re.sub(r'\$\(([^)]+)\)', r'$\1', value)
    
    return os.path.expandvars(os.path.expanduser(normalized))


base = resolve(os.getenv("BASE_CONTENT_DIR", ""))

if not base:
    sys.exit(
        "✗ BASE_CONTENT_DIR not set — is Doppler injecting vars? "
        "Run: make env-check"
    )

dirs = [
    resolve(os.getenv(key, ""))
    for key in (
        "SCRIPTS_DIR",
        "REPURPOSED_DIR",
        "ANALYTICS_DIR",
        "IDEAS_DIR",
    )
]

for directory in dirs:
    if directory:
        Path(directory).mkdir(parents=True, exist_ok=True)

ideas = resolve(os.getenv("IDEAS_DIR", ""))

if ideas:
    Path(ideas, "backlog.md").touch(exist_ok=True)

print(f"✓ Content directories created at {base}")