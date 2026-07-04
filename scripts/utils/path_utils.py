import os
import re
from pathlib import Path


def resolve(value: str) -> str:
    """Expand home-directory and environment variables in path-like values."""
    # Convert $(VAR) syntax to $VAR syntax so expandvars() can expand it.
    pattern: str = r"\$\(([^)]+)\)"
    fixed_pattern: str = r"$\1"

    if not value:
        return ""

    normalized: str = re.sub(pattern, fixed_pattern, value)

    return os.path.expandvars(os.path.expanduser(normalized))


def create_directories(base_dir: str, directory_keys: list[str], touch_keys: dict[str, str]) -> None:
    """Create directories and touch files from environment variables."""
    base: str = resolve(os.getenv(base_dir, ""))

    if not base:
        raise ValueError(f"{base_dir} not set — is Doppler injecting vars?")

    directories: list[str] = [resolve(os.getenv(key, "")) for key in directory_keys]

    for directory in directories:
        if directory:
            Path(directory).mkdir(parents=True, exist_ok=True)

    for directory, filename in touch_keys.items():
        dir_path: str = resolve(os.getenv(directory, ""))
        if dir_path:
            Path(dir_path, filename).touch(exist_ok=True)
