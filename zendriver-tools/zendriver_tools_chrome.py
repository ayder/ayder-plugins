"""Chrome executable resolution. zendriver's chrome-only search, with the
AYDER_BROWSER_EXECUTABLE override checked before use."""
import os
from pathlib import Path


class ChromeError(Exception):
    pass


def _search():
    # Outside the try: a missing zendriver must propagate as
    # ModuleNotFoundError, not read as "no Chrome found".
    from zendriver.core.config import find_executable
    try:
        return find_executable(browser="chrome")
    except Exception:
        return None


def resolve_executable() -> Path:
    override = os.environ.get("AYDER_BROWSER_EXECUTABLE")
    if override:
        if not os.path.isfile(override) or not os.access(override, os.X_OK):
            raise ChromeError(
                f"AYDER_BROWSER_EXECUTABLE={override!r} is not an existing "
                f"executable file")
        return Path(override)
    exe = _search()
    if not exe:
        raise ChromeError(
            "No Chrome/Chromium executable found. Install Google Chrome, or "
            "set AYDER_BROWSER_EXECUTABLE to a Chrome executable.")
    return Path(exe)
