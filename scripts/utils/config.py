"""Load declarative TOML config from scripts/config/.

Tunables (models, voice/render settings, pricing) and rule sets live in
``scripts/config/*.toml`` rather than as literals in code. Loaded values are
cached — config is read once per process.
"""

import tomllib
from functools import lru_cache
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    """Load and cache ``scripts/config/<name>.toml`` as a dict."""
    path = CONFIG_DIR / f"{name}.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)
