"""Argument validation. Every handler validates before anything else."""
import re

PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


class ValidationError(Exception):
    pass


def check_url(url):
    if not isinstance(url, str) or not (
        url.startswith("http://") or url.startswith("https://")
        or url == "about:blank"
    ):
        raise ValidationError(
            "url must be an http://, https:// or about:blank URL")


def check_profile(name):
    if name is None:
        return
    if not isinstance(name, str) or not PROFILE_RE.match(name) or name == "throwaway":
        raise ValidationError(
            "profile must match ^[a-z0-9][a-z0-9-]{0,31}$ and not be 'throwaway'")


def check_timeout(t):
    if not isinstance(t, int) or isinstance(t, bool) or not 1 <= t <= 120:
        raise ValidationError("timeout_seconds must be an integer from 1 to 120")


def check_max_chars(m):
    if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= 100000:
        raise ValidationError("max_chars must be an integer from 1 to 100000")


def check_bool(b, name):
    if not isinstance(b, bool):
        raise ValidationError(f"{name} must be a boolean")


def require_str(value, name):
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{name} is required and must be a non-empty string")


def require_browser(running: bool):
    if not running:
        raise ValidationError("No browser is running. Call browser_open first.")
