import importlib
import os
import subprocess
from typing import Callable, List, Tuple


def check_python_module(module_name: str, display_name: str | None = None) -> Tuple[bool, str]:
    try:
        importlib.import_module(module_name)
        label = display_name or module_name
        return True, f"✓ {label}"
    except Exception as exc:  # pragma: no cover - import failures vary by env
        label = display_name or module_name
        return False, f"✗ {label} missing: {exc}"


def check_doppler_cli() -> Tuple[bool, str]:
    try:
        result = subprocess.run(["doppler", "--version"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return False, "✗ doppler CLI not found — install from doppler.com/cli"

    if result.returncode == 0:
        return True, "✓ doppler CLI installed"
    return False, "✗ doppler CLI not found — install from doppler.com/cli"


def check_doppler_auth() -> Tuple[bool, str]:
    try:
        result = subprocess.run(["doppler", "me"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return False, "✗ doppler not authenticated — run: doppler login"

    if result.returncode == 0:
        return True, "✓ doppler authenticated"
    return False, "✗ doppler not authenticated — run: doppler login"


def check_env_var(name: str) -> Tuple[bool, str]:
    value = os.getenv(name, "")
    if value:
        return True, f"✓ {name}: {value}"
    return False, f"✗ {name} not set"


def render_statuses(statuses: List[Tuple[bool, str]]) -> None:
    for _, message in statuses:
        print(message)
