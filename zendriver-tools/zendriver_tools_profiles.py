"""Profile path safety: root containment, protected browser data areas,
0700 creation. Refusals happen before any directory is created (D18)."""
import os
import sys
from pathlib import Path


class ProfileError(Exception):
    pass


def profiles_root() -> Path:
    override = os.environ.get("AYDER_BROWSER_PROFILES_DIR")
    if override:
        return Path(override)
    return Path.home() / ".ayder" / "browser-profiles"


def _ident(path: Path):
    st = os.stat(path)
    return (st.st_dev, st.st_ino)


def _existing_ancestors(path: Path):
    cur = path
    while True:
        if cur.exists():
            yield cur
        if cur.parent == cur:
            return
        cur = cur.parent


def _protected_areas(env, platform: str, home: Path) -> list[Path]:
    areas = []
    if platform == "darwin":
        areas.append(home / "Library" / "Application Support")
    else:
        xdg = env.get("XDG_CONFIG_HOME")
        areas.append(Path(xdg) if xdg else home / ".config")
    for var in ("CHROME_CONFIG_HOME", "CHROME_USER_DATA_DIR"):
        if env.get(var):
            areas.append(Path(env[var]))
    return areas


def refuse_browser_data_areas(path: Path, env=None, platform=None) -> None:
    """Refuse a profile that is, contains, or lies inside a browser data
    area. Existing ancestors are compared by file identity (device+inode),
    never by string, so case-insensitive spellings cannot slip past."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    home = Path(env.get("HOME") or str(Path.home()))
    pr = Path(path).resolve()
    for area in _protected_areas(env, platform, home):
        ar = area.resolve()
        if ar.exists():
            aid = _ident(ar)
            # inside or is: an existing ancestor of the profile IS the area
            for anc in _existing_ancestors(pr):
                if _ident(anc) == aid:
                    raise ProfileError(
                        f"profile path lies in a protected browser data area: {area}")
            # contains: the profile IS an existing ancestor of the area
            if pr.exists():
                pid = _ident(pr)
                for anc in _existing_ancestors(ar):
                    if _ident(anc) == pid:
                        raise ProfileError(
                            f"profile path contains a protected browser data area: {area}")
        # string containment covers non-existing segments (and equality)
        if pr == ar or pr.is_relative_to(ar) or ar.is_relative_to(pr):
            raise ProfileError(
                f"profile path lies in a protected browser data area: {area}")


def check_profile_lock(profile_dir: Path) -> None:
    """POSIX Chrome marks a profile in use with a SingletonLock symlink to
    <hostname>-<pid>. Proceed only with no lock or a confirmed-stale one;
    anything else is in use. The lock is never removed or changed (D15)."""
    import socket

    lock = Path(profile_dir) / "SingletonLock"
    if not lock.is_symlink():
        if lock.exists():
            raise ProfileError("profile is in use (unreadable SingletonLock)")
        return
    try:
        target = os.readlink(lock)
        host, pid_s = target.rsplit("-", 1)
        pid = int(pid_s)
        if not host or pid <= 0:
            raise ValueError
    except (OSError, ValueError):
        raise ProfileError("profile is in use (unreadable SingletonLock)")
    if host != socket.gethostname():
        raise ProfileError("profile is in use (lock owned by another host)")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return  # confirmed stale: local host, PID not running
    except PermissionError:
        raise ProfileError("profile is in use (lock PID exists)")
    raise ProfileError("profile is in use (lock PID is running)")


def prepare_profile(name: str, platform=None) -> Path:
    """Resolve, check and (only then) create a persistent profile dir."""
    root = profiles_root()
    target = root / name
    rr = root.resolve()
    pr = target.resolve()  # follows symlinks even when the target exists
    if not pr.is_relative_to(rr):
        raise ProfileError("profile path escapes the profiles root")
    refuse_browser_data_areas(pr, platform=platform)
    created = not target.exists()
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    if created:
        os.chmod(target, 0o700)  # umask-independent
    return target
